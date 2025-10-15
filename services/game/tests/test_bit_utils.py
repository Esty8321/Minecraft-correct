# tests/test_color_utils.py
import torch
import importlib
import pytest

# tests/test_bit_utils.py
import os, sys
# ודא שהתיקייה services נמצאת ב-PYTHONPATH בזמן הריצה:
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from game import bits as cu

@pytest.fixture(autouse=True)
def configure_constants(monkeypatch):
    """
    Ensure the module under test has deterministic bit positions and dtype for tests.
    We monkeypatch the names that were imported from .settings in the module.
    """
    # choose simple bit positions for testing
    r0, r1 = 0, 1
    g0, g1 = 2, 3
    b0, b1 = 4, 5
    is_player_bit = 7

    # dtype
    monkeypatch.setattr(cu, "DTYPE", torch.uint8)

    # bit constants
    monkeypatch.setattr(cu, "BIT_R0", r0)
    monkeypatch.setattr(cu, "BIT_R1", r1)
    monkeypatch.setattr(cu, "BIT_G0", g0)
    monkeypatch.setattr(cu, "BIT_G1", g1)
    monkeypatch.setattr(cu, "BIT_B0", b0)
    monkeypatch.setattr(cu, "BIT_B1", b1)
    monkeypatch.setattr(cu, "BIT_IS_PLAYER", is_player_bit)

    # COLOR_BITS map matches how the code iterates in inc_color
    monkeypatch.setattr(cu, "COLOR_BITS", {"r": (r0, r1), "g": (g0, g1), "b": (b0, b1)})

    yield


def test_set_and_get_bit_true_false():
    v0 = torch.tensor(0, dtype=torch.uint8)
    # set bit 3 to 1
    v1 = cu.set_bit(v0, 3, True)
    assert int(v1.item()) == (1 << 3)

    # set bit 3 to 0 again
    v2 = cu.set_bit(v1, 3, False)
    assert int(v2.item()) == 0

def test_get_bit_single_positions():
    # value 5 => binary 00000101 => bits 0 and 2 are 1
    v = torch.tensor(5, dtype=torch.uint8)
    assert int(cu.get_bit(v, 0).item()) == 1
    assert int(cu.get_bit(v, 1).item()) == 0
    assert int(cu.get_bit(v, 2).item()) == 1

def test_set2_and_get2_basic():
    v0 = torch.tensor(0, dtype=torch.uint8)
    b0, b1 = cu.BIT_R0, cu.BIT_R1
    # set the two-bit field to 3 (binary 11)
    v1 = cu.set2(v0, b0, b1, 3)
    assert int(v1.item()) == 3  # because bits 0 and 1 set

    # read it back
    val = int(cu.get2(v1, b0, b1).item())
    assert val == 3

    # overwrite with 1 (01)
    v2 = cu.set2(v1, b0, b1, 1)
    assert int(cu.get2(v2, b0, b1).item()) == 1

def test_make_color_and_get2_each_channel():
    # create a color with r=1, g=2, b=3
    v = cu.make_color(1, 2, 3)
    assert int(cu.get2(v, cu.BIT_R0, cu.BIT_R1).item()) == 1
    assert int(cu.get2(v, cu.BIT_G0, cu.BIT_G1).item()) == 2
    assert int(cu.get2(v, cu.BIT_B0, cu.BIT_B1).item()) == 3

def test_inc_color_wraparound_and_sequence():
    # start with all channels at value 3 (max)
    v = cu.make_color(3, 3, 3)
    # inc_color should wrap each channel ((3+1) % 4 == 0)
    v2 = cu.inc_color(v)
    assert int(cu.get2(v2, cu.BIT_R0, cu.BIT_R1).item()) == 0
    assert int(cu.get2(v2, cu.BIT_G0, cu.BIT_G1).item()) == 0
    assert int(cu.get2(v2, cu.BIT_B0, cu.BIT_B1).item()) == 0

    # also test one-step increment from (0,0,0) -> (1,1,1)
    v_zero = cu.make_color(0, 0, 0)
    v_inc = cu.inc_color(v_zero)
    assert int(cu.get2(v_inc, cu.BIT_R0, cu.BIT_R1).item()) == 1
    assert int(cu.get2(v_inc, cu.BIT_G0, cu.BIT_G1).item()) == 1
    assert int(cu.get2(v_inc, cu.BIT_B0, cu.BIT_B1).item()) == 1

def test_with_and_without_player_bit():
    v0 = torch.tensor(0, dtype=torch.uint8)
    v_player = cu.with_player(v0)
    # player bit should be set
    assert int(cu.get_bit(v_player, cu.BIT_IS_PLAYER).item()) == 1

    # remove player bit
    v_no_player = cu.without_player(v_player)
    assert int(cu.get_bit(v_no_player, cu.BIT_IS_PLAYER).item()) == 0
