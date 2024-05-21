from collections import (
    Counter,
)
import typing as t
import sqlite3
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
from db.types import (
    FeaturePayload,
    Image,
    ImageAggregation,
)


# TODO:
# 1. Check code that it works, and check types
# 2. Use this in annotation
# 3. Make converter for existing features
# 4. Backup into jsonl
# 5. Remove Json DB
# 6. Cleanup after removal


class FeaturesTable:
    def __init__(
        self,
        path: t.Union[
            str,
            sqlite3.Connection,
        ],
    ) -> None:
        if isinstance(
            path,
            str,
        ):
            self._con = sqlite3.connect(path)
        else:
            self._con = path
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
    ) -> t.Iterable[t.Tuple[str, int,]]:
        if types:
            q = ", ".join(f"'{qt}'" for qt in types)
            res = self._con.execute(
                f"SELECT file, MAX(last_update) FROM features WHERE dirty > 0 AND type in ({q}) GROUP BY file"
            )
        else:
            res = self._con.execute(
                "SELECT file, MAX(last_update) FROM features WHERE dirty > 0 GROUP BY file"
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
        path: t.Union[
            str,
            sqlite3.Connection,
        ],
    ) -> None:
        if isinstance(
            path,
            str,
        ):
            self._con = sqlite3.connect(path)
        else:
            self._con = path
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
        for columns in [
            ["file"],
            ["feature_last_update"],
            ["timestamp"],
            ["tags"],
            ["classifications"],
            ["address_full"],
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
INSERT INTO gallery_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(file) DO UPDATE SET
  feature_last_update=excluded.feature_last_update,
  timestamp=excluded.timestamp,
  tags=excluded.tags,
  tags_probs=excluded.tags_probs,
  classifications=excluded.classifications,
  address_country=excluded.address_country,
  address_name=excluded.address_name,
  address_full=excluded.address_full
WHERE excluded.feature_last_update > gallery_index.feature_last_update""",
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
            ),
        )
        self._con.commit()

    def _matching_query(
        self,
        select: str,
        url: UrlParameters,
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
        if url.dateto:
            clauses.append("timestamp <= ?")
            variables.append(
                maybe_datetime_to_timestamp(None if url.dateto is None else url.dateto + timedelta(days=1))
            )
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

    def get_aggregate_stats(
        self,
        url: UrlParameters,
    ) -> ImageAggregation:
        # do aggregate query
        (select, variables,) = self._matching_query(
            "tags, classifications, address_name, address_country",
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
        """
        tag_cnt: t.Counter[str] = Counter()
        classifications_cnt: t.Counter[str] = Counter()
        address_cnt: t.Counter[str] = Counter()
        total = 0
        res = self._con.execute(
            query,
            variables,
        )
        while True:
            items = res.fetchmany(size=url.paging or 100)
            if not items:
                return ImageAggregation(
                    total,
                    address_cnt,
                    tag_cnt,
                    classifications_cnt,
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
                else:
                    raise Exception(f"Wrong type returned {type_}")

    def get_matching_images(
        self,
        url: UrlParameters,
    ) -> t.Iterable[Image]:
        # TODO: aggregations could be done separately
        (query, variables,) = self._matching_query(
            "file, timestamp, tags, tags_probs, classifications, address_country, address_name, address_full, feature_last_update",
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
                )
