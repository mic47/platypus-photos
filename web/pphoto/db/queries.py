import typing as t

from pphoto.data_model.base import StorableData, PathWithMd5
from pphoto.db.connection import PhotosConnection


class PhotosQueries:
    def __init__(self, con: PhotosConnection) -> None:
        self._con = con

    def get_not_annotated_files(self, models: t.List[t.Type[StorableData]]) -> t.List[PathWithMd5]:
        assert len(models) > 0, "You have to provide at least single model"
        clauses = [
            f"(type == '{model.__name__}' AND version == {model.current_version()})" for model in models
        ]
        clauses_str = "WHERE " + " OR ".join(clauses)
        ret = self._con.execute(
            f"""
SELECT
  files.path,
  files.md5
FROM
  files
  LEFT OUTER JOIN (
    SELECT
      md5,
      COUNT(DISTINCT type) AS correct_versions
    FROM
      features
    {clauses_str}
    GROUP BY md5
  ) AS fts
  ON files.md5 = fts.md5
WHERE correct_versions IS NULL OR correct_versions != ?
            """,
            (len(models),),
        )
        return [PathWithMd5(path, md5) for (path, md5) in ret.fetchall()]
