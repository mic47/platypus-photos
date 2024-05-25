import sys
import typing as t
from datetime import datetime, date
import os
import re

from data_model.config import Config, DirectoryMatchingConfig

# glob.glob(re.sub("^~/", os.environ["HOME"] + "/", '~/Camera/Camera/*jpg'))

DATE_TIME_FILE_REGEX = re.compile(
    "".join(
        [
            "^(?:|.*_)",
            "(?P<year>20[0-9][0-9])",
            "(?P<dsep>|-)",
            "(?P<month>[01][0-9])",
            "(?P=dsep)",
            "(?P<day>[0123][0-9])",
            "[-_ ]",
            "(?P<hour>[012][0-9])",
            "(?P<tsep>|-|:|[.])",
            "(?P<minute>[0-6][0-9])",
            "(?P=tsep)",
            "(?P<second>[0-6][0-9])",
            "(?:|_[0-9]{2,3}|(?:| )[(][0-9]{1,5}[)]|_[a-zA-Z]*|[-_][-_0-9]*|[.][.a-zA-Z]*)",
            "[.]",
            "(?:[^.]{2,5})$",
        ]
    ),
    re.IGNORECASE,
)


class PathDateExtractor:
    def __init__(self, config: DirectoryMatchingConfig):
        self._path_to_date = [(re.compile(x), parse_date(y)) for x, y in config.path_to_date.items()]
        self._no_date_in_path_filter = re.compile("|".join(config.no_date_in_path_filters))
        self._dated_directory = [verify_filter(re.compile(x)) for x in config.date_directory_filters]

    def extract_date(self, file: str) -> t.Optional[datetime]:
        filename = os.path.basename(file)
        match = DATE_TIME_FILE_REGEX.match(filename)
        try:
            if match is not None:
                date_ = datetime(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                    int(match.group("hour")),
                    int(match.group("minute")),
                    int(match.group("second")),
                )
                return date_
        # pylint: disable = broad-exception-caught
        except Exception as e:
            print("ERR", filename, e, file=sys.stderr)
        for ddf in self._dated_directory:
            try:
                match = ddf.match(file)
                if match is not None:
                    date_ = datetime(
                        int(match.group("year")),
                        int(match.group("month")),
                        int(match.group("day")),
                    )
                    return date_
            # pylint: disable = broad-exception-caught
            except Exception as e:
                print("ERR", filename, e, ddf, file=sys.stderr)
        for s, date_ in self._path_to_date:
            if s.search(file) is not None:
                return date_
        return None

    def should_be_ignored(self, file: str) -> bool:
        return self._no_date_in_path_filter.search(file) is not None


def parse_date(d: t.Union[date, datetime, str]) -> datetime:
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime(d.year, d.month, d.day)
    return datetime.strptime(d, "%Y-%m-%d")


def verify_filter(pattern: re.Pattern[str]) -> re.Pattern[str]:
    assert pattern.groupindex.get("year") is not None, f"Missing `year` in date patter in {pattern.pattern}"
    assert pattern.groupindex.get("month") is not None, f"Missing `month` in date patter in {pattern.pattern}"
    assert pattern.groupindex.get("day") is not None, f"Missing `day` in date patter in {pattern.pattern}"
    return pattern


def main() -> None:
    config = Config.load("config.yaml")
    ex = PathDateExtractor(config.directory_matching)

    total = 0
    with_date = 0
    without_date = 0
    unclassifiable = 0
    unclass = []
    for line in sys.stdin:
        total += 1
        line = line.strip()
        out = ex.extract_date(line)
        if out is None and not ex.should_be_ignored(line):
            unclassifiable += 1
            unclass.append(line)
        elif out is None:
            without_date += 1
        else:
            with_date += 1
            print(line, out)
    for l in unclass:
        print(l)
    print(
        f"with_date {100*with_date/total:5.2f}% without_date {100*without_date/total:5.2f} unclassifiable {100*unclassifiable/total:5.2f}"
    )
    print(f"{unclassifiable} out of {total} left")


if __name__ == "__main__":
    main()
