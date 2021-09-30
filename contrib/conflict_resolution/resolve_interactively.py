#!/usr/bin/env python3
"""Ask user to resolve a vdirsyncer sync conflict interactively.

Needs a way to ask the user.
The use of https://apps.kde.org/kdialog/ for GNU/Linix is hardcoded.

Depends on python>3.5 and KDialog.

Usage:
  Ensure the file executable and use it in the vdirsyncer.conf file, e.g.

  conflict_resolution = ["command", "/home/bern/vdirsyncer/resolve_interactively.py"]

This file is Free Software under the following license:
SPDX-License-Identifier: BSD-3-Clause
SPDX-FileCopyrightText: 2021 Intevation GmbH <https://intevation.de>
Author: <bernhard.reiter@intevation.de>
"""
import re
import subprocess
import sys
from pathlib import Path

KDIALOG = "/usr/bin/kdialog"

SUMMARY_PATTERN = re.compile("^(SUMMARY:.*)$", re.MULTILINE)


def get_summary(icalendar_text: str):
    """Get the first SUMMARY: line from an iCalendar text.

    Do not care about the line being continued.
    """
    match = re.search(SUMMARY_PATTERN, icalendar_text)
    return match[1]


def main(ical1_filename, ical2_filename):
    ical1 = ical1_filename.read_text()
    ical2 = ical2_filename.read_text()

    additional_args = ["--yes-label", "take first"]  # return code == 0
    additional_args += ["--no-label", "take second"]  # return code == 1
    additional_args += ["--cancel-label", "do not resolve"]  # return code == 2

    r = subprocess.run(
        args=[
            KDIALOG,
            "--warningyesnocancel",
            "There was a sync conflict, do you prefer the first entry: \n"
            f"{get_summary(ical1)}...\n(full contents: {ical1_filename})\n\n"
            "or the second entry:\n"
            f"{get_summary(ical2)}...\n(full contents: {ical2_filename})?",
        ]
        + additional_args
    )

    if r.returncode == 2:
        # cancel was pressed
        return  # shall lead to items not changed, because not copied

    if r.returncode == 0:
        # we want to take the first item, so overwrite the second
        ical2_filename.write_text(ical1)
    else:  # r.returncode == 1, we want the second item, so overwrite the first
        ical1_filename.write_text(ical2)


if len(sys.argv) != 3:
    sys.stdout.write(__doc__)
else:
    main(Path(sys.argv[1]), Path(sys.argv[2]))
