import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.db.gallery_index_table import GalleryIndexTable
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.db.cache import SQLiteCache
from pphoto.data_model.manual import ManualIdentities
from pphoto.data_model.face import FaceEmbeddings
from pphoto.db.files_table import FilesTable
from pphoto.db.features_table import FeaturesTable
from pphoto.db.identity_table import IdentityTable
from pphoto.db.directories_table import DirectoriesTable
from pphoto.remote_jobs.db import RemoteJobsTable

from pphoto.db.types_image import ImageAggregation, Image
from pphoto.db.types_location import LocationCluster, LocPoint, LocationBounds
from pphoto.db.types_file import FileRow
from pphoto.db.types_date import DateCluster, DateClusterGroupBy
from pphoto.db.types_directory import DirectoryStats
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams

Ser = t.TypeVar("Ser", bound=DataClassJsonMixin)


class ImageSqlDB:
    def __init__(
        self,
        photos_connection: PhotosConnection,
        gallery_connection: GalleryConnection,
        jobs_connection: JobsConnection,
    ) -> None:
        self._connections = [photos_connection, gallery_connection, jobs_connection]
        self._files_table = FilesTable(photos_connection)
        features_table = FeaturesTable(photos_connection)
        self._manual_identities = SQLiteCache(features_table, ManualIdentities, None)
        self.identities = IdentityTable(photos_connection)
        self._faces_embeddings = SQLiteCache(features_table, FaceEmbeddings, None)
        self._gallery_index = GalleryIndexTable(gallery_connection)
        self.jobs = RemoteJobsTable(jobs_connection)
        self._directories_table = DirectoriesTable(gallery_connection)
        self._hash_to_image: t.Dict[int, str] = {}
        self._md5_to_image: t.Dict[str, str] = {}

    def reconnect(self) -> None:
        for con in self._connections:
            con.reconnect()

    def check_unused(self) -> None:
        for con in self._connections:
            con.check_unused()

    def files(self, md5: str) -> t.List[FileRow]:
        return self._files_table.by_md5(md5)

    def get_path_from_hash(self, hsh: t.Union[int, str]) -> t.Optional[str]:
        if isinstance(hsh, int):
            return self._hash_to_image[hsh]
        r = self._md5_to_image.get(hsh)
        if r is not None:
            return r
        path = self._files_table.example_by_md5(hsh)
        if path is None:
            return None
        self._md5_to_image[hsh] = path.file
        return path.file

    def get_aggregate_stats(self, url: "SearchQuery") -> ImageAggregation:
        return self._gallery_index.get_aggregate_stats(url)

    def get_date_clusters(
        self, url: SearchQuery, group_by: t.List[DateClusterGroupBy], buckets: int
    ) -> t.List[DateCluster]:
        return self._gallery_index.get_date_clusters(url, group_by, buckets)

    def get_matching_directories(self, url: SearchQuery) -> t.List[DirectoryStats]:
        return self._gallery_index.get_matching_directories(url)

    def get_matching_md5(
        self,
        url: SearchQuery,
        has_location: t.Optional[bool] = None,
        has_manual_location: t.Optional[bool] = None,
        has_manual_text: t.Optional[bool] = None,
        has_manual_date: t.Optional[bool] = None,
    ) -> t.List[str]:
        return self._gallery_index.get_matching_md5(
            url, has_location, has_manual_location, has_manual_text, has_manual_date
        )

    def get_location_bounds(self, url: "SearchQuery") -> t.Optional[LocationBounds]:
        return self._gallery_index.get_location_bounds(url)

    def get_image_clusters(
        self,
        url: SearchQuery,
        top_left: LocPoint,
        bottom_right: LocPoint,
        latitude_resolution: float,
        longitude_resolution: float,
        over_fetch: float,
    ) -> t.List[LocationCluster]:
        return self._gallery_index.get_image_clusters(
            url, top_left, bottom_right, latitude_resolution, longitude_resolution, over_fetch
        )

    def get_face_embeddings(self, md5: str) -> t.Optional[FaceEmbeddings]:
        r = self._faces_embeddings.get(md5)
        if r is None or r.payload is None:
            return None
        return r.payload.p

    def get_manual_identities(self, md5: str) -> t.Optional[ManualIdentities]:
        r = self._manual_identities.get(md5)
        if r is None or r.payload is None:
            return None
        return r.payload.p

    def get_matching_images(
        self,
        query: SearchQuery,
        sort_params: SortParams,
        gallery_paging: GalleryPaging,
    ) -> t.Tuple[t.List[Image], bool]:
        return self._gallery_index.get_matching_images(query, sort_params, gallery_paging)

    def mark_annotated(self, md5s: t.List[str]) -> None:
        self._gallery_index.mark_annotated(md5s)
