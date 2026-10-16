"""The home screen greets the student by the time on their own clock."""

from __future__ import annotations

import pytest

from veritagnosis.states.auth_state import greeting_for


@pytest.mark.parametrize("hour, said", [
    (5, "Good morning"), (9, "Good morning"), (11, "Good morning"),
    (12, "Good afternoon"), (16, "Good afternoon"),
    (17, "Good evening"), (21, "Good evening"), (23, "Good evening"),
    (0, "Good evening"), (4, "Good evening"),      # 2am is not "morning"
])
def test_each_hour_gets_the_right_greeting(hour, said):
    assert greeting_for(hour) == said


@pytest.mark.parametrize("hour", [-1, 24, 99])
def test_before_the_browser_answers_it_just_says_hello(hour):
    assert greeting_for(hour) == "Hello"


def test_every_hour_of_the_day_is_covered():
    assert {greeting_for(h) for h in range(24)} == {
        "Good morning", "Good afternoon", "Good evening"}
