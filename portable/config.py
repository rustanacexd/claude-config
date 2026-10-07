import json
import math
import datetime
import tomllib

MISSING = object()


def equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if (
        isinstance(a, float)
        and isinstance(b, float)
        and math.isnan(a)
        and math.isnan(b)
    ):
        return True
    return type(a) is type(b) and a == b


def merge(previous, live, shared, path=(), conflicts=None):
    if equal(live, previous):
        return shared
    if isinstance(live, dict) and all(
        v is MISSING or isinstance(v, dict) for v in (previous, shared)
    ):
        old = {} if previous is MISSING else previous
        new = {} if shared is MISSING else shared
        result = {}
        for key in sorted(old.keys() | live.keys() | new.keys()):
            value = merge(
                old.get(key, MISSING),
                live.get(key, MISSING),
                new.get(key, MISSING),
                path + (key,),
                conflicts,
            )
            if value is not MISSING:
                result[key] = value
        return result
    if (
        conflicts is not None
        and not equal(previous, shared)
        and not equal(live, shared)
    ):
        conflicts.append(".".join(path))
    return live


def quote(value):
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def scalar(value):
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(scalar(v) for v in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(quote(k) + " = " + scalar(v) for k, v in value.items())
            + "}"
        )
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def render(config):
    lines = []

    def table(value, path):
        if path:
            lines.extend(["", "[" + ".".join(quote(k) for k in path) + "]"])
        for key, item in value.items():
            if not isinstance(item, dict):
                lines.append(quote(key) + " = " + scalar(item))
        for key, item in value.items():
            if isinstance(item, dict):
                table(item, path + (key,))

    table(config, ())
    data = ("\n".join(lines).lstrip("\n") + "\n").encode()
    if not equal(tomllib.loads(data.decode()), config):
        raise ValueError("TOML serialization changed the configuration")
    return data


def parse(data):
    return tomllib.loads(data.decode("utf-8"))
