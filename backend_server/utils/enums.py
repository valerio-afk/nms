from enum import Enum

class DistroFamilies(Enum):
    DEB="apt"
    RH="dnf"
    UNK="unk"