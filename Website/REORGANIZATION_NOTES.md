# Website application file organization

The large Streamlit application source has been divided into ordered source sections so each Python source file stays below 3,000 lines.

## Main application

- `app.py` remains the Streamlit entry point.
- `app_sections/` contains the original application source in execution order:
  1. `01_app_setup_and_data_app_part.py`
  2. `02_matchups_and_team_profiles_app_part.py`
  3. `03_storylines_and_themes_app_part.py`
  4. `04_weekly_dashboard_and_router_app_part.py`

## Preserved backup application

- `backup_app.py` remains a compatibility entry point for the previous backup application.
- `backup_app_sections/` contains its original source in execution order.

## Important implementation detail

The entry points execute each ordered section in the same global namespace. This is intentional: the original Streamlit script shares functions, constants, cached functions, and state across its sections. Keeping that shared namespace avoids changing the existing call relationships while making the source easier to navigate. Run the app through `app.py` as before; the section files are not standalone modules and should not be run or imported individually.

The original code statements were retained in order. Only the entry-point wrappers and file organization changed.
