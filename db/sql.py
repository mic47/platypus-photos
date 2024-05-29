from collections import (
    Counter,
)
import typing as t
import math
import sqlite3
from datetime import (
    datetime,
    timedelta,
)
import traceback

# TODO move to proper place
from gallery.utils import (
    maybe_datetime_to_timestamp,
)

# TODO: extract this type into query payload
from gallery.url import (
    UrlParameters,
)
from db.types import FeaturePayload, Image, ImageAggregation, LocationCluster, LocPoint


class Connection:
    def __init__(self, path: str, timeout: int = 120, check_same_thread: bool = True) -> None:
        self._path = path
        self._timeout = timeout
        self._check_same_thread = check_same_thread
        self._last_use = datetime.now()
        self._connection: t.Optional[sqlite3.Connection] = self._connect()
        self._disconnect_timeout = timedelta(seconds=10)

    def reconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = self._connect()

    def check_unused(self) -> None:
        if self._connection is None:
            return
        now = datetime.now()
        if now - self._last_use > self._disconnect_timeout:
            self._connection.close()
            self._connection = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=self._timeout, check_same_thread=self._check_same_thread)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def execute(
        self,
        sql: str,
        parameters: t.Optional[t.Sequence[t.Union[str, bytes, int, float, None]]] = None,
    ) -> sqlite3.Cursor:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        if parameters is None:
            return self._connection.execute(sql)
        return self._connection.execute(sql, parameters)

    def commit(self) -> None:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        return self._connection.commit()


class WrongAggregateTypeReturned(Exception):
    def __init__(self, type_: str) -> None:
        super().__init__(f"Wrong aggregate type returned: {type_}")
        self.type = type_


class FeaturesTable:
    def __init__(
        self,
        connection: Connection,
    ) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS features (
  type TEXT NOT NULL,
  file TEXT NOT NULL,
  version INT NOT NULL,
  last_update INTEGER NOT NULL,
  dirty INTEGER NOT NULL,
  payload BLOB NOT NULL,
  PRIMARY KEY (type, file)
) STRICT;
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_type_file ON features (type, file);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_file ON features (file);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_last_update ON features (last_update);
        """
        )

    def undirty(
        self,
        path: str,
        types: t.List[str],
        max_last_update: float,
    ) -> None:
        q = ", ".join(f"'{qt}'" for qt in types)
        (query, param,) = (
            f"UPDATE features SET dirty = 0 WHERE dirty > 0 AND file = ? AND type in ({q}) AND last_update <= ?",
            (
                path,
                max_last_update,
            ),
        )
        self._con.execute(
            query,
            param,
        )
        self._con.commit()

    def dirty_files(
        self,
        types: t.List[str],
        limit: int = 1000,
    ) -> t.Iterable[t.Tuple[str, int,]]:
        if types:
            q = ", ".join(f"'{qt}'" for qt in types)
            res = self._con.execute(
                f"SELECT file, MAX(last_update) FROM features WHERE dirty > 0 AND type in ({q}) GROUP BY file LIMIT {limit}"
            )
        else:
            res = self._con.execute(
                "SELECT file, MAX(last_update) FROM features WHERE dirty > 0 GROUP BY file LIMIT {limit}"
            )
        while True:
            items = res.fetchmany()
            if not items:
                return
            yield from items

    def get_payload(
        self,
        type_: str,
        key: str,
    ) -> t.Optional[FeaturePayload[bytes]]:
        res = self._con.execute(
            "SELECT rowid, payload, last_update, version FROM features WHERE type = ? AND file = ?",
            (
                type_,
                key,
            ),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            payload,
            last_update,
            version,
        ) = res
        return FeaturePayload(
            payload,
            version,
            last_update,
            rowid,
        )

    def add(
        self,
        payload: bytes,
        type_: str,
        path: str,
        version: int,
    ) -> None:
        self._con.execute(
            """
INSERT INTO features VALUES (?, ?, ?, strftime('%s'), 1, ?)
ON CONFLICT(type, file) DO UPDATE SET
  version=excluded.version,
  last_update=excluded.last_update,
  dirty=excluded.dirty,
  payload=excluded.payload
WHERE excluded.version > features.version""",
            (
                type_,
                path,
                version,
                payload,
            ),
        )
        self._con.commit()


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
  file TEXT NOT NULL,
  feature_last_update INT NOT NULL,
  timestamp INTEGER,
  tags TEXT,
  tags_probs TEXT,
  classifications TEXT,
  address_country TEXT,
  address_name TEXT,
  address_full TEXT,
  PRIMARY KEY (file)
) STRICT;"""
        )
        try:
            self._con.execute("ALTER TABLE gallery_index ADD COLUMN latitude REAL;")
        except sqlite3.OperationalError:
            traceback.print_exc()
        try:
            self._con.execute("ALTER TABLE gallery_index ADD COLUMN longitude REAL;")
        except sqlite3.OperationalError:
            traceback.print_exc()
        try:
            self._con.execute("ALTER TABLE gallery_index ADD COLUMN altitude REAL;")
        except sqlite3.OperationalError:
            traceback.print_exc()
        try:
            self._con.execute("ALTER TABLE gallery_index ADD COLUMN version INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
            traceback.print_exc()
        try:
            self._con.execute("ALTER TABLE gallery_index ADD COLUMN md5 TEXT;")
        except sqlite3.OperationalError:
            traceback.print_exc()
        for columns in [
            ["file"],
            ["feature_last_update"],
            ["timestamp"],
            ["tags"],
            ["classifications"],
            ["address_full"],
            ["latitude"],
            ["longitude"],
            ["altitude"],
            ["version"],
            ["md5"],
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
INSERT INTO gallery_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(file) DO UPDATE SET
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
  md5=excluded.md5
WHERE
  excluded.feature_last_update > gallery_index.feature_last_update
  OR excluded.version > gallery_index.version
""",
            (
                omg.path,
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
                omg.md5,
            ),
        )
        self._con.commit()

    def old_version_files(
        self,
        limit: int = 1000,
    ) -> t.Iterable[str]:
        res = self._con.execute(
            f"SELECT file FROM gallery_index WHERE version < ? GROUP BY file LIMIT {limit}",
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
    ) -> t.Tuple["str", t.List[t.Union[str, int, float, None,]],]:
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
        if url.directory:
            clauses.append("file like ?")
            variables.append(f"{url.directory}%")
        if url.dateto:
            clauses.append("timestamp <= ?")
            variables.append(
                maybe_datetime_to_timestamp(None if url.dateto is None else url.dateto + timedelta(days=1))
            )
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

    def path_by_hash(self, hsh: str) -> t.Optional[str]:
        res = self._con.execute("SELECT file FROM gallery_index where md5 = ? LIMIT 1", (hsh,)).fetchone()
        if res is None:
            return None
        return t.cast(str, res[0])

    def get_aggregate_stats(
        self,
        url: UrlParameters,
    ) -> ImageAggregation:
        # do aggregate query
        (select, variables,) = self._matching_query(
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
                    if type_ not in position:
                        position[type_] = (count, count)
                    else:
                        x = position[type_]
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
    ) -> t.Iterable[Image]:
        # TODO: aggregations could be done separately
        (query, variables,) = self._matching_query(
            "file, timestamp, tags, tags_probs, classifications, address_country, address_name, address_full, feature_last_update, latitude, longitude, altitude, version, md5",
            url,
        )
        if url.paging:
            query = f"{query}\nORDER BY timestamp\nDESC LIMIT {url.paging}\nOFFSET {url.paging * url.page}"
        res = self._con.execute(
            query,
            variables,
        )
        while True:
            items = res.fetchmany(size=url.paging)
            if not items:
                return
            for (
                file,
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
                md5,
            ) in items:
                yield Image(
                    file,
                    None if timestamp is None else datetime.fromtimestamp(timestamp),  # TODO convert
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
                    md5,
                )


def round_to_significant_digits(value: float, significant_digits: int) -> float:
    return round(value, significant_digits - int(math.floor(math.log10(abs(value)))) - 1)
