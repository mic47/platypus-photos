from collections import (
    Counter,
)
import typing as t
import math
from datetime import (
    datetime,
    timedelta,
)

# TODO move to proper place
from gallery.utils import (
    maybe_datetime_to_timestamp,
)

# TODO: extract this type into query payload
from gallery.url import (
    UrlParameters,
)
from db.connection import Connection
from db.types import Image, ImageAggregation, LocationCluster, LocPoint, DateCluster


class WrongAggregateTypeReturned(Exception):
    def __init__(self, type_: str) -> None:
        super().__init__(f"Wrong aggregate type returned: {type_}")
        self.type = type_


class GalleryIndexTable:
    def __init__(
        self,
        connection: Connection,
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
            ["version"],
        ]:
            name = f"gallery_index_idx_{'_'.join(columns)}"
            cols_str = ", ".join(columns)
            self._con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON gallery_index ({cols_str});")

    def add(
        self,
        omg: Image,
    ) -> None:
        tags = sorted(list((omg.tags or {}).items()))
        self._con.execute(
            """
INSERT INTO gallery_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
  version=excluded.version
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
                omg.address_country,
                omg.address_name,
                omg.address_full,
                omg.latitude,
                omg.longitude,
                omg.altitude,
                omg.version,
            ),
        )
        self._con.commit()

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

    def _matching_query(
        self,
        select: str,
        url: UrlParameters,
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
        if url.datefrom:
            clauses.append("timestamp >= ?")
            variables.append(maybe_datetime_to_timestamp(url.datefrom))
        if url.dateto:
            clauses.append("timestamp <= ?")
            variables.append(
                maybe_datetime_to_timestamp(None if url.dateto is None else url.dateto + timedelta(days=1))
            )
        if url.directory:  # TODO: this does not work, fix it
            pass
            # clauses.append("file like ?")
            # variables.append(f"{url.directory}%")
        if url.tsfrom:
            clauses.append("timestamp >= ?")
            variables.append(url.tsfrom)
        if url.tsto:
            clauses.append("timestamp <= ?")
            variables.append(url.tsto)
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

    def get_date_clusters(self, url: UrlParameters, buckets: int) -> t.List[DateCluster]:
        minmax_select = self._matching_query("timestamp", url)
        minmax = self._con.execute(
            f"""
            SELECT MIN(timestamp), MAX(timestamp) FROM ({minmax_select[0]})
            """,
            minmax_select[1],
        ).fetchone()
        if minmax is None:
            return []
        bucket_size = max(1.0, (1.0 + float(minmax[1]) - float(minmax[0])) / buckets)
        final_subselect_query = self._matching_query("timestamp, md5", url)
        final = self._con.execute(
            f"""
SELECT
  (bucket) * {bucket_size} + {minmax[0]} AS bucket_min,
  (bucket + 1) * {bucket_size} + {minmax[0]} AS bucket_max,
  min_timestamp,
  max_timestamp,
  avg_timestamp,
  total,
  example_md5
FROM (
  SELECT
    CAST((timestamp - {minmax[0]})/ {bucket_size} AS INT) AS bucket,
    MIN(timestamp) AS min_timestamp,
    MAX(timestamp) AS max_timestamp,
    AVG(timestamp) AS avg_timestamp,
    COUNT(1) as total,
    MIN(md5) as example_md5
  FROM
    ({final_subselect_query[0]}) sl
  WHERE timestamp IS NOT NULL
  GROUP BY bucket

) fl
            """,
            final_subselect_query[1],
        )
        return [
            DateCluster(
                example_path_md5, bucket_min, bucket_max, min_timestamp, max_timestamp, avg_timestamp, total
            )
            for (
                bucket_min,
                bucket_max,
                min_timestamp,
                max_timestamp,
                avg_timestamp,
                total,
                example_path_md5,
            ) in final.fetchall()
        ]

    def get_image_clusters(
        self,
        url: UrlParameters,
        top_left: LocPoint,
        bottom_right: LocPoint,
        latitude_resolution: float,
        longitude_resolution: float,
        over_fetch: float,
    ) -> t.List[LocationCluster]:
        lats = [top_left.latitude, bottom_right.latitude]
        longs = [top_left.longitude, bottom_right.longitude]
        lat_scale = round_to_significant_digits((max(lats) - min(lats)) / latitude_resolution, 3)
        lon_scale = round_to_significant_digits((max(longs) - min(longs)) / longitude_resolution, 3)
        over_fetch_lat = (max(lats) - min(lats)) * over_fetch
        over_fetch_long = (max(longs) - min(longs)) * over_fetch
        select_items, variables = self._matching_query(
            f"""
            address_name, address_country, latitude, longitude,
            md5, classifications,
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
  min(md5),
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
            example_file_md5,
            example_classification,
        ) in res:
            out.append(
                LocationCluster(
                    example_file_md5,
                    example_classification,
                    total,
                    address_name,
                    address_country,
                    LocPoint(max_latitude, max_longitude),
                    LocPoint(min_latitude, min_longitude),
                    LocPoint(avg_latitude, avg_longitude),
                )
            )
        return out

    def get_aggregate_stats(
        self,
        url: UrlParameters,
        _extra_query_for_tests: str = "",
    ) -> ImageAggregation:
        # do aggregate query
        (
            select,
            variables,
        ) = self._matching_query(
            "tags, classifications, address_name, address_country, latitude, longitude, altitude",
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
SELECT "addrn", address_name, COUNT(1) FROM matched_images WHERE address_name IS NOT NULL GROUP BY address_name
UNION ALL
SELECT "addrc", address_country, COUNT(1) FROM matched_images WHERE address_country IS NOT NULL GROUP BY address_country
UNION ALL
SELECT "lat", 'max', MAX(latitude) FROM matched_images WHERE latitude IS NOT NULL
UNION ALL
SELECT "lat", 'min', MIN(latitude) FROM matched_images WHERE latitude IS NOT NULL
UNION ALL
SELECT "lon", 'max', MAX(longitude) FROM matched_images WHERE longitude IS NOT NULL
UNION ALL
SELECT "lon", 'min', MIN(longitude) FROM matched_images WHERE longitude IS NOT NULL
UNION ALL
SELECT "alt", 'max', MAX(altitude) FROM matched_images WHERE altitude IS NOT NULL
UNION ALL
SELECT "alt", 'min', MIN(altitude) FROM matched_images WHERE altitude IS NOT NULL
{_extra_query_for_tests}
        """
        tag_cnt: t.Counter[str] = Counter()
        classifications_cnt: t.Counter[str] = Counter()
        address_cnt: t.Counter[str] = Counter()
        total = 0
        res = self._con.execute(
            query,
            variables,
        )
        position: t.Dict[str, t.Tuple[float, float]] = {}
        while True:
            items = res.fetchmany(size=url.paging or 100)
            if not items:
                return ImageAggregation(
                    total,
                    address_cnt,
                    tag_cnt,
                    classifications_cnt,
                    position.get("lat"),
                    position.get("lon"),
                    position.get("alt"),
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
                elif type_ in [
                    "addrn",
                    "addrc",
                ]:
                    address_cnt[value] += count
                elif type_ in [
                    "lat",
                    "lon",
                    "alt",
                ]:
                    if count is None:
                        continue
                    x = position.get(type_, (count, count))
                    if value == "min":
                        position[type_] = (count, x[1])
                    elif value == "max":
                        position[type_] = (x[0], count)
                    else:
                        raise WrongAggregateTypeReturned(f"{type_}:{value}")
                else:
                    raise WrongAggregateTypeReturned(type_)

    def get_matching_images(
        self,
        url: UrlParameters,
    ) -> t.Tuple[t.List[Image], bool]:
        # TODO: aggregations could be done separately
        actual_paging = url.paging + 1
        (
            query,
            variables,
        ) = self._matching_query(
            "md5, timestamp, tags, tags_probs, classifications, address_country, address_name, address_full, feature_last_update, latitude, longitude, altitude, version",
            url,
        )
        if url.paging:
            query = f"{query}\nORDER BY timestamp\nDESC LIMIT {actual_paging}\nOFFSET {url.paging * url.page}"
        res = self._con.execute(
            query,
            variables,
        )
        items = res.fetchall()
        has_extra_data = len(items) > url.paging
        output = []
        for (
            md5,
            timestamp,
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
        ) in items[: url.paging]:
            output.append(
                Image(
                    md5,
                    None if timestamp is None else datetime.fromtimestamp(timestamp),  # TODO convert
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
                    address_country,
                    address_name,
                    address_full,
                    feature_last_update,
                    latitude,
                    longitude,
                    altitude,
                    version,
                )
            )
        return output, has_extra_data


def round_to_significant_digits(value: float, significant_digits: int) -> float:
    return round(value, significant_digits - int(math.floor(math.log10(abs(value)))) - 1)
