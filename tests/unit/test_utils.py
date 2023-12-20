from app.utils import load_class_object_from_string


def test_load_class_object_from_string():
    cls = load_class_object_from_string("app.openfoodfacts.ResultProcessor")
    assert isinstance(cls, type)
    assert cls.__name__ == "ResultProcessor"
