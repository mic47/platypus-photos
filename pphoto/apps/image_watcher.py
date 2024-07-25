import argparse
import asyncio
import json
import sys
import traceback
import typing as t

import asyncinotify
import tqdm

from pphoto.data_model.base import PathWithMd5
from pphoto.data_model.config import Config, DBFilesConfig
from pphoto.data_model.manual import ManualIdentity
from pphoto.db.features_table import FeaturesTable
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.db.files_table import FilesTable
from pphoto.db.identity_table import IdentityTable
from pphoto.db.queries import PhotosQueries
from pphoto.annots.annotator import Annotator
from pphoto.annots.date import PathDateExtractor
from pphoto.communication.server import start_image_server_loop, ImportDirectory, RefreshJobs
from pphoto.remote_jobs.types import TaskId, RemoteTask, ManualAnnotationTask, RemoteJobType
from pphoto.remote_jobs.db import RemoteJobsTable
from pphoto.file_mgmt.jobs import Jobs, JobType, IMPORT_PRIORITY, DEFAULT_PRIORITY, REALTIME_PRIORITY
from pphoto.file_mgmt.queues import Queues, Queue
from pphoto.gallery.reindexer import Reindexer
from pphoto.utils import assert_never, Lazy
from pphoto.utils.alive import Alive
from pphoto.utils.files import get_paths, expand_vars_in_path
from pphoto.utils.progress_bar import ProgressBar
from pphoto.communication.server import RemoteExecutorQueue, start_annotation_remote_worker_loop


class GlobalContext:
    def __init__(
        self,
        jobs: Jobs,
        files: FilesTable,
        remote_jobs: RemoteJobsTable,
        queues: Queues,
    ) -> None:
        self.queues = queues
        self.jobs = jobs
        self.remote_jobs = remote_jobs
        self.files = files


@Alive(persistent=True, key=[0])
async def worker(name: str, context: GlobalContext, queue: Queue, /) -> None:
    while True:
        # Get a "work item" out of the queue.
        item = await queue.get()
        path, type_ = item.payload
        try:
            if type_ == JobType.CHEAP_FEATURES:
                assert isinstance(path, PathWithMd5)
                context.jobs.cheap_features(path, recompute_location=False)
            elif type_ == JobType.IMAGE_TO_TEXT:
                assert isinstance(path, PathWithMd5)
                await context.jobs.image_to_text(path)
            elif type_ == JobType.ADD_MANUAL_ANNOTATION:
                if isinstance(path, RemoteTask) and isinstance(path.payload, ManualAnnotationTask):
                    context.jobs.add_manual_annotation(path)
                else:
                    assert False, "Wrong type for ADD_MANUAL_ANNOTATION"
            elif type_ == JobType.FACE_CLUSTER_ANNOTATION:
                if (
                    isinstance(path, RemoteTask)
                    and isinstance(path.payload, list)
                    and all(isinstance(x, ManualIdentity) for x in path.payload)
                ):
                    new_identities = context.jobs.face_cluster_task(path)
                    if new_identities[1]:
                        context.queues.enqueue_path(
                            [(new_identities, JobType.COMPUTE_FACE_EMBEDDING_FOR_MANUAL_ANNOTATION)],
                            item.priority,
                        )
                else:
                    assert False, "Wrong type for FACE_CLUSTER_ANNOTATION"
            elif type_ == JobType.COMPUTE_FACE_EMBEDDING_FOR_MANUAL_ANNOTATION:
                if (
                    isinstance(path, tuple)
                    and len(path) == 2
                    and isinstance(path[0], PathWithMd5)
                    and isinstance(path[1], list)
                    and all(isinstance(x, ManualIdentity) for x in path[1])
                ):
                    await context.jobs.compute_additional_face_embedding(path[0], path[1])
                else:
                    assert False, "Wrong type for FACE_CLUSTER_ANNOTATION"
            else:
                assert_never(type_)
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing path in ", name, path, e, file=sys.stderr)
            if isinstance(path, PathWithMd5):
                context.queues.mark_failed(path)
        finally:
            # Notify the queue that the "work item" has been processed.
            context.queues.get_progress_bar(type_, item.priority).update(1)
            queue.task_done()
            # So that we gave up place for other workers too
            await asyncio.sleep(0.001)


@Alive(persistent=True, key=[0])
async def manual_annotation_worker(
    name: str, input_queue: asyncio.Queue[RefreshJobs], context: GlobalContext, /
) -> None:
    visited: t.Set[TaskId] = set()
    while True:
        refresh_job = await input_queue.get()
        try:
            unfinished_tasks = context.remote_jobs.unfinished_tasks()
            for task in unfinished_tasks:
                if task.id_ in visited:
                    continue
                if task.type_ == RemoteJobType.MASS_MANUAL_ANNOTATION:
                    try:
                        parsed_task = task.map(ManualAnnotationTask.from_json)
                    # pylint: disable-next = bare-except
                    except:
                        traceback.print_exc()
                        print("Error while parsing manual task", name, task)
                        continue

                    context.queues.enqueue_path(
                        [(parsed_task, JobType.ADD_MANUAL_ANNOTATION)], REALTIME_PRIORITY
                    )
                elif task.type_ == RemoteJobType.FACE_CLUSTER_ANNOTATION:
                    try:
                        face_cluster_task = task.map(
                            lambda data: [ManualIdentity.from_dict(x) for x in json.loads(data)]
                        )
                    # pylint: disable-next = bare-except
                    except:
                        traceback.print_exc()
                        print("Error while parsing manual task", name, task)
                        continue

                    context.queues.enqueue_path(
                        [(face_cluster_task, JobType.FACE_CLUSTER_ANNOTATION)], REALTIME_PRIORITY
                    )
                else:
                    assert_never(task.type_)
                visited.add(task.id_)
        # pylint: disable-next = bare-except
        except:
            traceback.print_exc()
            print("Error in manual annotation worker", name, refresh_job)
            continue


@Alive(persistent=True, key=[0])
async def inotify_worker(name: str, dirs: t.List[str], context: GlobalContext, /) -> None:
    with asyncinotify.Inotify() as inotify:
        for dir_ in dirs:
            inotify.add_watch(
                expand_vars_in_path(dir_),
                asyncinotify.Mask.CREATE | asyncinotify.Mask.MOVE,
            )
        async for event in inotify:
            if event.path is None:
                continue
            try:
                path = event.path.absolute().resolve().as_posix()
                path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add=True)
                if path_with_md5 is None:
                    continue
                context.queues.enqueue_path_skipped_known(path_with_md5, REALTIME_PRIORITY)
            # pylint: disable-next = bare-except
            except:
                traceback.print_exc()
                print("Error in inotify worker", name)
                continue


@Alive(persistent=True, key=[])
async def reingest_directories_worker(context: GlobalContext, config: Config, /) -> None:
    total_for_reingest = 0
    while True:
        await context.queues.cheap_features.join()
        found_something = False
        for path in get_paths(config.input_patterns, config.input_directories):
            if context.files.by_path(path) is not None:
                continue
            path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add=True)
            if path_with_md5 is None:
                continue
            context.queues.enqueue_path_skipped_known(path_with_md5, DEFAULT_PRIORITY)
            total_for_reingest += 1
            if total_for_reingest % 1000 == 0:
                await asyncio.sleep(0.001)
            found_something = True
        if found_something:
            context.queues.update_progress_bars()
        # Check for new features once every 8 hours
        await asyncio.sleep(3600 * 8)


@Alive(persistent=True, key=[])
async def managed_worker_and_import_worker(
    context: GlobalContext, queue: asyncio.Queue[ImportDirectory], /
) -> None:
    # TODO: check for new files in managed folders, and add them. Run it from time to time
    progress_bar = Lazy(lambda: context.queues.get_progress_bar(JobType.CHEAP_FEATURES, IMPORT_PRIORITY))
    while True:
        import_command = await queue.get()
        try:
            paths = list(get_paths([], [import_command.import_path]))
            if paths:
                progress_bar.get().add_to_total(len(paths))
                progress_bar.get().update_total()
            enqueued = False
            for path in paths:
                try:
                    action = context.jobs.import_file(path, import_command.mode)
                    if action is not None:
                        enqueued = True
                        context.queues.enqueue_path(
                            [(action.path_with_md5, t) for t in action.job_types], action.priority
                        )
                # pylint: disable-next = broad-exception-caught
                except Exception as e:
                    traceback.print_exc()
                    print("Error while importing path", path, e, file=sys.stderr)
                    continue
                finally:
                    progress_bar.get().update(1)
                    # So that we gave up place for other workers too
                    await asyncio.sleep(0.001)
            if enqueued and paths:
                context.queues.update_progress_bars()
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while pricessing import request", import_command, e, file=sys.stderr)
            continue
        finally:
            # So that we gave up place for other workers too
            await asyncio.sleep(0.001)


@Alive(persistent=True, key=[])
async def reindex_gallery(reindexer: Reindexer, /) -> None:
    # Allow other tasks to start
    await asyncio.sleep(0.001)
    sleep_time = 1
    max_sleep_time = 64
    progress_bar = ProgressBar("Reindexing gallery", permanent=True)
    while True:
        try:
            done = await reindexer.load(progress=progress_bar)
            if done <= 100:
                sleep_time = min(sleep_time * 2, max_sleep_time)
            else:
                sleep_time = 1
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while trying to refresh data in db:", e)
            sleep_time = 1
            print("Reconnecting")
            reindexer.reconnect()
        await asyncio.sleep(sleep_time)


# pylint: disable-next = too-many-statements
async def main() -> None:
    files_config = DBFilesConfig()
    parser = argparse.ArgumentParser(prog="Photo annotator")
    parser.add_argument("--config", default="config.yaml", type=str)
    parser.add_argument("--db", default=files_config.photos_db, type=str)
    parser.add_argument("--remote-annotator-port", default=8001, type=int)
    parser.add_argument("--image-to-text-workers", default=3, type=int)
    args = parser.parse_args()
    config = Config.load(args.config)
    photos_connection = PhotosConnection(args.db)
    gallery_connection = GalleryConnection(files_config.gallery_db)
    jobs_connection = JobsConnection(files_config.jobs_db)
    reindexer = Reindexer(PathDateExtractor(config.directory_matching), photos_connection, gallery_connection)
    features = FeaturesTable(photos_connection)
    files = FilesTable(photos_connection)
    identities = IdentityTable(photos_connection)

    @Alive(persistent=True, key=[])
    async def check_db_connection() -> None:
        while True:
            photos_connection.check_unused()
            reindexer.check_unused()
            Lazy.check_ttl()
            await asyncio.sleep(10)

    import_queue: asyncio.Queue[ImportDirectory] = asyncio.Queue()
    refresh_queue: asyncio.Queue[RefreshJobs] = asyncio.Queue()
    await start_image_server_loop(refresh_queue, import_queue, "unix-domain-socket")
    remote_annotator_queue: RemoteExecutorQueue = asyncio.Queue()
    await start_annotation_remote_worker_loop(remote_annotator_queue, args.remote_annotator_port)

    tasks = []
    tasks.append(asyncio.create_task(check_db_connection()))
    tasks.append(asyncio.create_task(reindex_gallery(reindexer)))

    annotator = Annotator(
        config.directory_matching, files_config, features, identities, remote_annotator_queue
    )
    remote_jobs_table = RemoteJobsTable(jobs_connection)
    jobs = Jobs(config.managed_folder, files, remote_jobs_table, PhotosQueries(photos_connection), annotator)
    queues = Queues()
    context = GlobalContext(jobs, files, remote_jobs_table, queues)

    # Fix inconsistencies in the DB before we start.
    context.jobs.fix_in_progress_moved_files_at_startup()
    context.jobs.fix_imported_files_at_startup()

    unannotated = context.jobs.find_unannotated_files()
    for action in tqdm.tqdm(unannotated, desc="Enqueuing unannotated files"):
        context.queues.enqueue_path([(action.path_with_md5, t) for t in action.job_types], action.priority)
    del unannotated
    context.queues.update_progress_bars()

    # Starting async tasks
    tasks.append(asyncio.create_task(manual_annotation_worker("manual-annotation", refresh_queue, context)))
    tasks.append(asyncio.create_task(managed_worker_and_import_worker(context, import_queue)))
    tasks.append(asyncio.create_task(reingest_directories_worker(context, config)))
    for i in range(1):
        task = asyncio.create_task(worker(f"worker-cheap-{i}", context, queues.cheap_features))
        tasks.append(task)
    for i in range(args.image_to_text_workers):
        task = asyncio.create_task(worker(f"worker-image-to-text-{i}", context, queues.image_to_text))
        tasks.append(task)
    tasks.append(asyncio.create_task(inotify_worker("watch-files", config.watched_directories, context)))
    try:
        while True:
            await asyncio.sleep(3600 * 24 * 365)
            print("Wow, it's on for 365 days!🚀", file=sys.stderr)
    finally:
        for task in tasks:
            task.cancel()
        # Wait until all worker tasks are cancelled.
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
