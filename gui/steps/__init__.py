# -*- coding: utf-8 -*-
"""Шаги мастера."""

from gui.steps.step_build import StepBuild
from gui.steps.step_conditions import StepConditions
from gui.steps.step_learners import StepLearners
from gui.steps.step_passport import StepPassport
from gui.steps.step_plan import StepPlan

__all__ = [
    "StepPassport",
    "StepLearners",
    "StepPlan",
    "StepConditions",
    "StepBuild",
]
