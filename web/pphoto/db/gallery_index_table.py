from collections import (
    Counter,
)
import copy
import itertools
import typing as t
import math
from datetime import datetime

# TODO move to proper place
from pphoto.gallery.utils import (
    maybe_datetime_to_timestamp,
)

# TODO: extract this type into query payload
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy
from pphoto.utils import assert_never
from pphoto.data_model.manual import ManualText, ManualLocation, ManualDate
from pphoto.db.connection import GalleryConnection
from pphoto.db.directories_table import DirectoriesTable
from pphoto.db.types_location import LocationCluster, LocPoint, LocationBounds
from pphoto.db.types_date import DateCluster, DateClusterGroup, DateClusterGroupBy
from pphoto.db.types_directory import (
    DirectoryStats,
)
from pphoto.db.types_image import (
    Image,
    ImageAddress,
    ImageAggregation,
)


class WrongAggregateTypeReturned(Exception):
    def __init__(self, type_: str) -> None:
        super().__init__(f"Wrong aggregate type returned: {type_}")
        self.type = type_


_DATE_BUCKET_SIZES_SECONDS = [
    1,
    60,
    15 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    24 * 60 * 60,
    7 * 24 * 60 * 60,
    30 * 24 * 60 * 60,
    90 * 24 * 60 * 60,
    180 * 24 * 60 * 60,
    365.25 * 24 * 60 * 60,
]


class GalleryIndexTable:
    def __init__(
        self,
        connection: GalleryConnection,
    ) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        # TODO: store tags as text and tags as list of items
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS gallery_index (
  md5 TEXT NOT NULL,
  feature_last_update INT NOT NULL,
  timestamp INTEGER,
  tags TEXT,
  tags_probs TEXT,
  classifications TEXT,
  address_country TEXT,
  address_name TEXT,
  address_full TEXT,
  latitude REAL,
  longitude REAL,
  altitude REAL,
  version INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (md5)
) STRICT;"""
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN manual_features TEXT NOT NULL DEFAULT ""
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN being_annotated INTEGER NOT NULL DEFAULT 0
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN camera TEXT
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN software TEXT
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN extension TEXT NOT NULL DEFAULT "jpg"
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE gallery_index ADD COLUMN identity TEXT
        """
        )
        for columns in [
            ["md5"],
            ["feature_last_update"],
            ["timestamp"],
            ["tags"],
            ["classifications"],
            ["address_full"],
            ["latitude"],
            ["longitude"],
            ["altitude"],
            ["manual_features"],
            ["version"],
            ["camera"],
            ["identity"],
        ]:
            name = f"gallery_index_idx_{'_'.join(columns)}"
            cols_str = ", ".join(columns)
            self._con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON gallery_index ({cols_str});")
        # Just init this table
        DirectoriesTable(self._con)

    def add(
        self,
        omg: Image,
    ) -> None:
        tags = sorted(list((omg.tags or {}).items()))
        self._con.execute(
            """
INSERT INTO gallery_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
ON CONFLICT(md5) DO UPDATE SET
  feature_last_update=excluded.feature_last_update,
  timestamp=excluded.timestamp,
  tags=excluded.tags,
  tags_probs=excluded.tags_probs,
  classifications=excluded.classifications,
  address_country=excluded.address_country,
  address_name=excluded.address_name,
  address_full=excluded.address_full,
  latitude=excluded.latitude,
  longitude=excluded.longitude,
  altitude=excluded.altitude,
  version=excluded.version,
  manual_features=excluded.manual_features,
  being_annotated=excluded.being_annotated,
  camera=excluded.camera,
  software=excluded.software,
  extension=excluded.extension,
  identity=excluded.identity
WHERE
  excluded.version > gallery_index.version
  OR (
    excluded.version >= gallery_index.version
    AND excluded.feature_last_update > gallery_index.feature_last_update
  )
""",
            (
                omg.md5,
                omg.dependent_features_last_update,
                maybe_datetime_to_timestamp(omg.date),
                ":".join([t for t, _ in tags]),
                ":".join([f"{p:.4f}" for _, p in tags]),
                omg.classifications,
                omg.address.country,
                omg.address.name,
                omg.address.full,
                omg.latitude,
                omg.longitude,
                omg.altitude,
                omg.version,
                f',{",".join(omg.manual_features)},',
                omg.camera,
                omg.software,
                omg.extension,
                f',{",".join(omg.identities)},',
            ),
        )
        self._con.commit()

    def old_versions_md5_total(
        self,
    ) -> int:
        res = self._con.execute(
            "SELECT COUNT(1) FROM gallery_index WHERE version < ?",
            (Image.current_version(),),
        ).fetchone()
        assert res is not None
        return int(res[0])

    def old_versions_md5(
        self,
        limit: int = 1000,
    ) -> t.Iterable[str]:
        res = self._con.execute(
            f"SELECT md5 FROM gallery_index WHERE version < ? GROUP BY md5 LIMIT {limit}",
            (Image.current_version(),),
        )
        while True:
            items = res.fetchmany()
            if not items:
                return
            yield from (item for (item,) in items)

    def mark_annotated(self, md5s: t.List[str]) -> None:
        self._con.executemany(
            "UPDATE gallery_index SET being_annotated = 1 WHERE md5 = ?",
            [(x,) for x in md5s],
        )
        self._con.commit()

    def _matching_query(
        self,
        select: str,
        url: SearchQuery,
        extra_clauses: t.Optional[t.List[t.Tuple[str, t.List[t.Union[str, int, float, None]]]]] = None,
    ) -> t.Tuple[
        "str",
        t.List[
            t.Union[
                str,
                int,
                float,
                None,
            ]
        ],
    ]:
        clauses = []
        variables: t.List[
            t.Union[
                str,
                int,
                float,
                None,
            ]
        ] = []
        timestamp_column = "timestamp"
        if url.timestamp_trans:
            timestamp_column = f"({url.timestamp_trans})"
        select = (
            select.replace("#as#timestamp#", f"{timestamp_column} AS timestamp")
            .replace("#timestamp#", timestamp_column)
            .replace("#timestamp_transformed#", f"timestamp != ({timestamp_column}) as timestamp_transformed")
        )
        if url.addr:
            clauses.append("address_full like ?")
            variables.append(f"%{url.addr}%")
        if url.cls:
            clauses.append("classifications like ?")
            variables.append(f"%{url.cls}%")
        if url.tag:
            for tag in url.tag.split(","):
                clauses.append("tags like ?")
                variables.append(f"%{tag}%")
        if url.identity:
            for ident in url.identity.split(","):
                clauses.append("identity like ?")
                variables.append(f"%,{ident},%")
        if url.directory:
            clauses.append("md5 in (SELECT md5 FROM directories WHERE directory like ?)")
            variables.append(f"{url.directory}%")
        if url.camera:
            clauses.append("camera like ?")
            variables.append(f"%{url.camera}%")
        if url.tsfrom:
            clauses.append(f"{timestamp_column} >= ?")
            variables.append(url.tsfrom)
        if url.tsto:
            clauses.append(f"{timestamp_column} <= ?")
            variables.append(url.tsto)
        if url.skip_with_location:
            clauses.append("address_full IS NULL")
        if url.skip_being_annotated:
            clauses.append("being_annotated = 0")
        for txt, vrs in extra_clauses or []:
            clauses.append(f"({txt})")
            variables.extend(vrs)
        if clauses:
            where = "WHERE " + " AND ".join(clauses)
        else:
            where = ""
        query = f"""
        SELECT {select}
        FROM gallery_index
        {where}
        """
        return (
            query,
            variables,
        )

    def get_matching_md5(
        self,
        url: SearchQuery,
        has_location: t.Optional[bool] = None,
        has_manual_location: t.Optional[bool] = None,
        has_manual_text: t.Optional[bool] = None,
        has_manual_date: t.Optional[bool] = None,
    ) -> t.List[str]:
        extra_clauses: t.List[t.Tuple[str, t.List[str | int | float | None]]] = []
        if has_location is not None:
            if has_location:
                extra_clauses.append(("address_full IS NOT NULL", []))
            else:
                extra_clauses.append(("address_full IS NULL", []))
        if has_manual_location is not None:
            if has_manual_location:
                extra_clauses.append((f"manual_features LIKE '%,{ManualLocation.__name__},%'", []))
            else:
                extra_clauses.append((f"manual_features NOT LIKE '%,{ManualLocation.__name__},%'", []))
        if has_manual_text is not None:
            if has_manual_text:
                extra_clauses.append((f"manual_features LIKE '%,{ManualText.__name__},%'", []))
            else:
                extra_clauses.append((f"manual_features NOT LIKE '%,{ManualText.__name__},%'", []))
        if has_manual_date is not None:
            if has_manual_date:
                extra_clauses.append((f"manual_features LIKE '%,{ManualDate.__name__},%'", []))
            else:
                extra_clauses.append((f"manual_features NOT LIKE '%,{ManualDate.__name__},%'", []))

        (query, params) = self._matching_query("md5", url, extra_clauses)
        return [x for (x,) in self._con.execute(query, params).fetchall()]

    def get_date_clusters(
        self, url: SearchQuery, group_by: t.List[DateClusterGroupBy], buckets: int
    ) -> t.List[DateCluster]:
        minmax_select = self._matching_query("#as#timestamp#", url)
        minmax = self._con.execute(
            f"""
            SELECT MIN(timestamp), MAX(timestamp) FROM ({minmax_select[0]})
            """,
            minmax_select[1],
        ).fetchone()
        if minmax is None or minmax[0] is None or minmax[1] is None:
            return []
        diff = float(minmax[1]) - float(minmax[0])
        bucket_size_base = max(1.0, (1.0 + diff) / buckets)
        bucket_size = next(
            (x for x in _DATE_BUCKET_SIZES_SECONDS if x >= bucket_size_base), _DATE_BUCKET_SIZES_SECONDS[-1]
        )
        original_url = url
        url = copy.copy(url)
        if url.tsfrom:
            url.tsfrom -= diff / 2
        if url.tsto:
            url.tsto += diff / 2

        country_col = "NULL AS address_country"
        camera_col = "NULL AS camera"
        has_loc_col = "NULL AS has_location"
        address_name_col = "NULL AS address_name"
        for g in group_by:
            if g == DateClusterGroupBy.COUNTRY:
                country_col = "address_country"
            elif g == DateClusterGroupBy.CAMERA:
                camera_col = "camera"
            elif g == DateClusterGroupBy.HAS_LOCATION:
                has_loc_col = "address_country IS NOT NULL as has_location"
            elif g == DateClusterGroupBy.ADDRESS_NAME:
                address_name_col = "address_name"
            else:
                assert_never(g)

        final_subselect_query = self._matching_query(
            f"#as#timestamp#, md5, extension, {country_col}, {camera_col}, {has_loc_col}, {address_name_col}, #timestamp# < ? OR #timestamp# > ? as overfetched",
            url,
        )
        final_params = tuple(
            itertools.chain(
                [original_url.tsfrom or minmax[0], original_url.tsto or minmax[1]], final_subselect_query[1]
            )
        )
        final = self._con.execute(
            f"""
SELECT
  (bucket) * {bucket_size} + {minmax[0]} AS bucket_min,
  (bucket + 1) * {bucket_size} + {minmax[0]} AS bucket_max,
  overfetched,
  min_timestamp,
  max_timestamp,
  avg_timestamp,
  total,
  example_md5_with_extension,
  address_country,
  camera,
  has_location,
  address_name
FROM (
  SELECT
    CAST((timestamp - {minmax[0]})/ {bucket_size} AS INT) AS bucket,
    overfetched,
    MIN(timestamp) AS min_timestamp,
    MAX(timestamp) AS max_timestamp,
    AVG(timestamp) AS avg_timestamp,
    COUNT(1) as total,
    MIN(md5 || "." || extension) as example_md5_with_extension,
    IIF(overfetched, NULL, address_country) AS address_country,
    IIF(overfetched, NULL, camera) AS camera,
    IIF(overfetched, NULL, has_location) AS has_location,
    IIF(overfetched, NULL, address_name) AS address_name
  FROM
    ({final_subselect_query[0]}) sl
  WHERE timestamp IS NOT NULL
  GROUP BY bucket, overfetched, address_country, camera, has_location, address_name

) fl
            """,
            final_params,
        )
        return [
            DateCluster(
                example_path_md5_with_extension.split(".", maxsplit=1)[0],
                example_path_md5_with_extension.split(".", maxsplit=1)[1],
                bucket_min,
                bucket_max,
                bool(overfetched),
                min_timestamp,
                max_timestamp,
                avg_timestamp,
                total,
                DateClusterGroup(
                    address_name,
                    address_country,
                    camera,
                    bool(has_location) if has_location is not None else None,
                ),
            )
            for (
                bucket_min,
                bucket_max,
                overfetched,
                min_timestamp,
                max_timestamp,
                avg_timestamp,
                total,
                example_path_md5_with_extension,
                address_country,
                camera,
                has_location,
                address_name,
            ) in final.fetchall()
        ]

    def get_image_clusters(
        self,
        url: SearchQuery,
        top_left: LocPoint,
        bottom_right: LocPoint,
        latitude_resolution: float,
        longitude_resolution: float,
        over_fetch: float,
    ) -> t.List[LocationCluster]:
        lats = [top_left.latitude, bottom_right.latitude]
        longs = [top_left.longitude, bottom_right.longitude]
        if latitude_resolution == 0:
            latitude_resolution = 0.01
        if longitude_resolution == 0:
            longitude_resolution = 0.01
        lat_scale = round_to_significant_digits((max(lats) - min(lats)) / latitude_resolution, 3)
        lon_scale = round_to_significant_digits((max(longs) - min(longs)) / longitude_resolution, 3)
        over_fetch_lat = (max(lats) - min(lats)) * over_fetch
        over_fetch_long = (max(longs) - min(longs)) * over_fetch
        select_items, variables = self._matching_query(
            f"""
            address_name, address_country, latitude, longitude,
            md5, extension, classifications, #as#timestamp#,
            round(latitude/{lat_scale})*{lat_scale} as cluster_lat,
            round(longitude/{lon_scale})*{lon_scale} as cluster_lon
        """,
            url,
            [
                (
                    "latitude BETWEEN ? AND ?",
                    [bottom_right.latitude - over_fetch_lat, top_left.latitude + over_fetch_lat],
                ),
                (
                    "longitude BETWEEN ? AND ?",
                    [top_left.longitude - over_fetch_long, bottom_right.longitude + over_fetch_long],
                ),
            ],
        )
        query = f"""
SELECT
  address_name, address_country,
  min(latitude), max(latitude),
  min(longitude), max(longitude),
  avg(latitude), avg(longitude),
  count(1),
  MIN(md5 || "." || extension) as example_md5_with_extension,
  min(timestamp),
  max(timestamp),
  max(classifications)
FROM (
  {select_items}
)
WHERE
  latitude IS NOT NULL
  AND longitude IS NOT NULL
GROUP BY
  address_name, address_country, cluster_lat, cluster_lon
        """
        res = self._con.execute(query, variables)
        out = []
        for (
            address_name,
            address_country,
            min_latitude,
            max_latitude,
            min_longitude,
            max_longitude,
            avg_latitude,
            avg_longitude,
            total,
            example_file_md5_with_extension,
            min_timestamp,
            max_timestamp,
            example_classification,
        ) in res:
            (example_file_md5, example_file_extension) = example_file_md5_with_extension.split(
                ".", maxsplit=1
            )
            out.append(
                LocationCluster(
                    example_file_md5,
                    example_file_extension,
                    example_classification,
                    total,
                    address_name,
                    address_country,
                    min_timestamp,
                    max_timestamp,
                    LocPoint(max_latitude, max_longitude),
                    LocPoint(min_latitude, min_longitude),
                    LocPoint(avg_latitude, avg_longitude),
                )
            )
        return out

    def get_location_bounds(self, url: SearchQuery) -> t.Optional[LocationBounds]:
        (
            select,
            variables,
        ) = self._matching_query(
            "tags, classifications, address_name, address_country, latitude, longitude, altitude",
            url,
        )
        query = f"""
WITH matched_images as ({select})
SELECT
  MAX(latitude) as max_latitude,
  MIN(longitude) as min_longitude,
  MIN(latitude) as min_latitude,
  MAX(longitude) as max_longitude
FROM
  matched_images
        """
        res = self._con.execute(
            query,
            variables,
        ).fetchone()
        if res is None:
            return None
        if any(x is None for x in res):
            return None
        return LocationBounds(
            LocPoint(res[0], res[1]),
            LocPoint(res[2], res[3]),
        )

    def get_aggregate_stats(
        self,
        url: SearchQuery,
        _extra_query_for_tests: str = "",
    ) -> ImageAggregation:
        # do aggregate query
        (
            select,
            variables,
        ) = self._matching_query(
            "tags, classifications, address_name, address_country, camera, identity",
            url,
        )
        query = f"""
WITH matched_images AS ({select})
SELECT "total", null, COUNT(1) FROM matched_images
UNION ALL
SELECT "cls", classifications, COUNT(1) FROM matched_images GROUP BY classifications
UNION ALL
SELECT "tag", tags, COUNT(1) FROM matched_images GROUP BY tags
UNION ALL
SELECT "ident", identity, COUNT(1) FROM matched_images GROUP BY identity
UNION ALL
SELECT "addrn", address_name, COUNT(1) FROM matched_images WHERE address_name IS NOT NULL GROUP BY address_name
UNION ALL
SELECT "addrc", address_country, COUNT(1) FROM matched_images WHERE address_country IS NOT NULL GROUP BY address_country
UNION ALL
SELECT "cam", camera, COUNT(1) FROM matched_images GROUP BY camera
{_extra_query_for_tests}
        """
        tag_cnt: t.Counter[str] = Counter()
        classifications_cnt: t.Counter[str] = Counter()
        address_cnt: t.Counter[str] = Counter()
        cameras_cnt: t.Counter[t.Optional[str]] = Counter()
        identity_cnt: t.Counter[t.Optional[str]] = Counter()
        total = 0
        res = self._con.execute(
            query,
            variables,
        )
        while True:
            items = res.fetchmany()
            if not items:
                return ImageAggregation(
                    total,
                    address_cnt,
                    tag_cnt,
                    classifications_cnt,
                    cameras_cnt,
                    identity_cnt,
                )
            for (
                type_,
                value,
                count,
            ) in items:
                if type_ == "total":
                    total = count
                elif type_ == "cls":
                    if not value:
                        continue
                    for c in value.split(";"):
                        classifications_cnt[c] += count
                elif type_ == "tag":
                    if not value:
                        continue
                    for c in value.split(":"):
                        tag_cnt[c] += count
                elif type_ == "ident":
                    if not value:
                        continue
                    for c in value.split(","):
                        if c:
                            identity_cnt[c] += count
                elif type_ == "cam":
                    cameras_cnt[value] += count
                elif type_ in [
                    "addrn",
                    "addrc",
                ]:
                    address_cnt[value] += count
                else:
                    raise WrongAggregateTypeReturned(type_)

    def get_matching_images(
        self,
        url: SearchQuery,
        sort_params: SortParams,
        gallery_paging: GalleryPaging,
    ) -> t.Tuple[t.List[Image], bool]:
        # TODO: aggregations could be done separately
        actual_paging = gallery_paging.paging + 1
        (
            query,
            variables,
        ) = self._matching_query(
            "md5, extension, #as#timestamp#, #timestamp_transformed#, tags, tags_probs, classifications, address_country, address_name, address_full, feature_last_update, latitude, longitude, altitude, version, manual_features, being_annotated, camera, software, identity",
            url,
        )
        sort_by = None
        if sort_params.sort_by == SortBy.TIMESTAMP:
            sort_by = "timestamp"
        elif sort_params.sort_by == SortBy.RANDOM:
            sort_by = "RANDOM()"
        else:
            assert_never(sort_params.sort_by)

        if gallery_paging.paging:
            query = f"{query}\nORDER BY {sort_by}\n{sort_params.order.value} LIMIT {actual_paging}\nOFFSET {gallery_paging.paging * gallery_paging.page}"
        res = self._con.execute(
            query,
            variables,
        )
        items = res.fetchall()
        has_extra_data = len(items) > gallery_paging.paging
        output = []
        for (
            md5,
            extension,
            timestamp,
            timestamp_transformed,
            tags,
            tags_probs,
            classifications,
            address_country,
            address_name,
            address_full,
            feature_last_update,
            latitude,
            longitude,
            altitude,
            version,
            manual_features,
            being_annotated,
            camera,
            software,
            identity,
        ) in items[: gallery_paging.paging]:
            output.append(
                Image(
                    md5,
                    extension,
                    None if timestamp is None else datetime.fromtimestamp(timestamp),  # TODO convert
                    bool(timestamp_transformed),
                    (
                        None
                        if not tags
                        else dict(
                            zip(
                                tags.split(":"),
                                map(
                                    float,
                                    tags_probs.split(":"),
                                ),
                            )
                        )
                    ),
                    None if not classifications else classifications,
                    ImageAddress(
                        address_country,
                        address_name,
                        address_full,
                    ),
                    feature_last_update,
                    latitude,
                    longitude,
                    altitude,
                    [] if manual_features is None else [x for x in manual_features.split(",") if x],
                    bool(being_annotated),
                    camera,
                    software,
                    [x for x in identity.split(",") if x] if identity is not None else [],
                    version,
                )
            )
        return output, has_extra_data

    def get_matching_directories(self, url: SearchQuery) -> t.List[DirectoryStats]:
        (match_query, match_params) = self._matching_query(
            "md5, address_full, #as#timestamp#, being_annotated", url
        )
        ret = self._con.execute(
            f"""
SELECT
  directory,
  COUNT(directories.md5) as total,
  SUM(gallery.address_full IS NOT NULL) AS has_location,
  SUM(timestamp IS NOT NULL) AS has_timestamp,
  SUM(being_annotated) AS being_annotated,
  MIN(timestamp) AS since,
  MAX(timestamp) as until
FROM directories JOIN ({match_query}) AS gallery
ON directories.md5 = gallery.md5
WHERE gallery.md5 IS NOT NULL
GROUP BY directory
            """,
            match_params,
        ).fetchall()
        return [
            DirectoryStats(directory, total, has_location, has_timestamp, being_annotated, since, until)
            for (directory, total, has_location, has_timestamp, being_annotated, since, until) in ret
        ]


def round_to_significant_digits(value: float, significant_digits: int) -> float:
    if value == 0:
        return value
    return round(value, significant_digits - int(math.floor(math.log10(abs(value)))) - 1)
