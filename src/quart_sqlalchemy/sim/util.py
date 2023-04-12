import logging
import numbers

from hashids import Hashids


logger = logging.getLogger(__name__)


class CryptographyError(Exception):
    pass


class DecryptionError(CryptographyError):
    pass


def one(input_list):
    if len(input_list) != 1:
        raise ValueError(f"Expected a list of length 1, got {len(input_list)}")
    return input_list[0]


class ObjectID:
    hashids = Hashids(min_length=12)

    def __init__(self, input_value):
        if input_value is None:
            raise ValueError("ObjectID cannot be None")
        elif isinstance(input_value, ObjectID):
            self._source_id = input_value._decoded_id
        elif isinstance(input_value, str):
            self._source_id = self._decode(input_value)
        elif isinstance(input_value, numbers.Number):
            try:
                input_value = int(input_value)
            except (ValueError, TypeError):
                pass

            self._source_id = input_value
            self._encode()

    @property
    def _encoded_id(self):
        return self._encode()

    @property
    def _decoded_id(self):
        return self._source_id

    def __eq__(self, other):
        if isinstance(other, ObjectID):
            return self._decoded_id == other._decoded_id and self._encoded_id == other._encoded_id
        elif isinstance(other, int):
            return self._decoded_id == other
        elif isinstance(other, str):
            return self._encoded_id == other
        else:
            return False

    def __lt__(self, other):
        if isinstance(other, ObjectID):
            return self._decoded_id < other._decoded_id
        return False

    def __hash__(self):
        return hash(tuple([self._encoded_id, self._decoded_id]))

    def __str__(self):
        return "{encoded_id}".format(encoded_id=self._encoded_id)

    def __int__(self):
        return self._decoded_id

    def __repr__(self):
        return f"{type(self).__name__}({self._decoded_id})"

    def __json__(self):
        return self.__str__()

    def _encode(self):
        if isinstance(self._source_id, int):
            return self.hashids.encode(self._source_id)
        else:
            return self._source_id

    def encode(self):
        return self._encoded_id

    def _decode(self, value):
        if isinstance(value, int):
            return value
        else:
            return self.hashids.decode(value)[0]

    def decode(self):
        return self._decoded_id

    def decode_str(self):
        return str(self._decoded_id)
