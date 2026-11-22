"""
Diagmote - Behave tests configuration.
Copyright (C) 2026 Gabriel Jacinto

Diagmote is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Diagmote is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Diagmote. If not, see <https://www.gnu.org/licenses/>.
"""


def after_scenario(context, scenario):
    if hasattr(context, "temp_dir"):
        context.temp_dir.cleanup()
