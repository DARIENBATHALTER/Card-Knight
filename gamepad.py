"""Shared gamepad state — updated by the main event loop."""

_hat:         set = set()   # directions from d-pad hat
_axis:        set = set()   # directions from left analog stick
buttons_held: set = set()   # joystick button indices currently held


def update_hat(hx: int, hy: int) -> None:
    _hat.clear()
    if hx > 0:   _hat.add('right')
    elif hx < 0: _hat.add('left')
    if hy > 0:   _hat.add('up')      # pygame hat Y: +1 = up
    elif hy < 0: _hat.add('down')


def update_axis(axis: int, value: float, deadzone: float = 0.4) -> None:
    if axis == 0:
        _axis.discard('left');  _axis.discard('right')
        if value < -deadzone:   _axis.add('left')
        elif value > deadzone:  _axis.add('right')
    elif axis == 1:
        _axis.discard('up');    _axis.discard('down')
        if value < -deadzone:   _axis.add('up')
        elif value > deadzone:  _axis.add('down')


def active() -> set:
    """Return union of hat and stick directions currently held."""
    return _hat | _axis
