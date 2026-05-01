from datetime import datetime, timedelta
import calendar

def calculate_travel_dates(preferred_month: str, stay_days: int) -> dict:
    """
    Given a preferred month string (e.g. 'August 2026' or 'August') and a stay duration,
    calculates exact arrival and departure dates. If year is missing, assumes current year.
    Defaults to the 15th of the month.
    """
    try:
        # Try to parse "Month Year"
        parsed_date = datetime.strptime(preferred_month, "%B %Y")
    except ValueError:
        try:
            # Try to parse "Month"
            parsed_date = datetime.strptime(preferred_month, "%B")
            parsed_date = parsed_date.replace(year=datetime.now().year)
        except ValueError:
            # Fallback to current month if parsing fails
            parsed_date = datetime.now()

    arrival_date = parsed_date.replace(day=15)
    departure_date = arrival_date + timedelta(days=stay_days)

    return {
        "arrival_date": arrival_date.strftime("%Y-%m-%d"),
        "departure_date": departure_date.strftime("%Y-%m-%d")
    }
