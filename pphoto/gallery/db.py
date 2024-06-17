import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.db.gallery_index_table import GalleryIndexTable
from pphoto.db.connection import PhotosConnection, GalleryConnection
from pphoto.db.files_table import FilesTable
from pphoto.db.directories_table import DirectoriesTable

from pphoto.db.types_image import ImageAggregation, Image
from pphoto.db.types_location import LocationCluster, LocPoint
from pphoto.db.types_file import FileRow
from pphoto.db.types_date import DateCluster
from pphoto.db.types_directory import DirectoryStats
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams

Ser = t.TypeVar("Ser", bound=DataClassJsonMixin)


class ImageSqlDB:
    def __init__(self, photos_connection: PhotosConnection, gallery_connection: GalleryConnection) -> None:
        # TODO: this should be a feature with loader
        self._p_con = photos_connection
        self._g_con = gallery_connection
        self._files_table = FilesTable(self._p_con)
        self._gallery_index = GalleryIndexTable(self._g_con)
        self._directories_table = DirectoriesTable(self._g_con)
        self._hash_to_image: t.Dict[int, str] = {}
        self._md5_to_image: t.Dict[str, str] = {}

    def reconnect(self) -> None:
        self._p_con.reconnect()
        self._g_con.reconnect()

    def check_unused(self) -> None:
        self._p_con.check_unused()
        self._g_con.check_unused()

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

    def get_date_clusters(self, url: SearchQuery, buckets: int) -> t.List[DateCluster]:
        return self._gallery_index.get_date_clusters(url, buckets)

    def get_matching_directories(self, url: SearchQuery) -> t.List[DirectoryStats]:
        return self._gallery_index.get_matching_directories(url)

    def get_matching_md5(
        self,
        url: SearchQuery,
        has_location: t.Optional[bool] = None,
        has_manual_location: t.Optional[bool] = None,
        has_manual_text: t.Optional[bool] = None,
    ) -> t.List[str]:
        return self._gallery_index.get_matching_md5(url, has_location, has_manual_location, has_manual_text)

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

    def get_matching_images(
        self,
        query: SearchQuery,
        sort_params: SortParams,
        gallery_paging: GalleryPaging,
    ) -> t.Tuple[t.List[Image], bool]:
        return self._gallery_index.get_matching_images(query, sort_params, gallery_paging)
