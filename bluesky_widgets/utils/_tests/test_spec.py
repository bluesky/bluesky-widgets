import pickle
import uuid as uuid_module

from ..spec import define_spec


Example = define_spec("Example", ["a", "b"])


def test_field_names_as_string():
    Thing = define_spec("Thing", "a b")
    Thing(a=1, b=2)


def test_spec_uuid():
    "A spec should have an auto-generated uuid."
    example = Example(a=1, b=2)
    assert example.a == 1
    assert example.b == 2
    assert isinstance(example.uuid, uuid_module.UUID)


def test_spec_hashable():
    "A spec is hashable even when its contents are mutable."
    example = Example(a=1, b=[])
    hash(example)


def test_pickelable():
    "Test that a spec is pickleable, just like namedtuple from which it is derived."
    # Note: As with namedtuple, it's important that Example is defined *at
    # module scope* above.
    example = Example(a=1, b=2)
    serialized = pickle.dumps(example)
    deserialized = pickle.loads(serialized)
    assert example is not deserialized
    assert example == deserialized
