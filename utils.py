"""
Utility functions for data type consistency in the AI receptionist system.
This module provides standardized functions for handling time formats, user IDs,
and timezone conversions to ensure consistency across the application.
"""

import re
import uuid
from datetime import datetime
from typing import Optional, Union
import pytz

# Define Indian Standard Time (IST) timezone
IST = pytz.timezone('Asia/Kolkata')

def format_time_for_db(time_str: str) -> str:
    """
    Ensures time is in HH:MM:SS format for database operations.
    
    Args:
        time_str: A string representing time in various formats (HH:MM, HH:MM:SS, etc.)
        
    Returns:
        A string in HH:MM:SS format
        
    Examples:
        >>> format_time_for_db("14:30")
        "14:30:00"
        >>> format_time_for_db("2:30 PM")
        "14:30:00"
        >>> format_time_for_db("14:30:45")
        "14:30:45"
    """
    # Handle ISO format timestamps (common in API responses)
    iso_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', time_str)
    if iso_match:
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S')
        except ValueError:
            pass
    
    # Check if time is in 12-hour format with AM/PM
    am_pm_match = re.match(r'(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)', time_str, re.IGNORECASE)
    if am_pm_match:
        hour = int(am_pm_match.group(1))
        minute = int(am_pm_match.group(2))
        second = int(am_pm_match.group(3)) if am_pm_match.group(3) else 0
        
        # Convert to 24-hour format
        if am_pm_match.group(4).upper() == 'PM' and hour < 12:
            hour += 12
        elif am_pm_match.group(4).upper() == 'AM' and hour == 12:
            hour = 0
            
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    # Check if time is in 24-hour format without seconds
    hour_minute_match = re.match(r'(\d{1,2}):(\d{2})$', time_str)
    if hour_minute_match:
        hour = int(hour_minute_match.group(1))
        minute = int(hour_minute_match.group(2))
        return f"{hour:02d}:{minute:02d}:00"
    
    # Check if time is already in HH:MM:SS format
    full_time_match = re.match(r'(\d{1,2}):(\d{2}):(\d{2})$', time_str)
    if full_time_match:
        hour = int(full_time_match.group(1))
        minute = int(full_time_match.group(2))
        second = int(full_time_match.group(3))
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    # If format is not recognized, try to parse with datetime
    try:
        # Try various formats
        for fmt in ('%H:%M', '%I:%M %p', '%H:%M:%S', '%I:%M:%S %p'):
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime('%H:%M:%S')
            except ValueError:
                continue
        
        # If all parsing attempts fail, raise an exception
        raise ValueError(f"Time format not recognized: {time_str}")
    except Exception as e:
        # If all else fails, return the original string with a warning
        print(f"Warning: Could not format time string '{time_str}': {e}")
        return time_str

def validate_user_id(user_id: Union[str, uuid.UUID]) -> str:
    """
    Validates and formats user_id consistently as a string.
    
    Args:
        user_id: A string or UUID object representing a user ID
        
    Returns:
        A validated string representation of the UUID
        
    Raises:
        ValueError: If the user_id is not a valid UUID format
        
    Examples:
        >>> validate_user_id("123e4567-e89b-12d3-a456-426614174000")
        "123e4567-e89b-12d3-a456-426614174000"
        >>> validate_user_id(uuid.UUID("123e4567-e89b-12d3-a456-426614174000"))
        "123e4567-e89b-12d3-a456-426614174000"
    """
    try:
        # If it's already a UUID object, convert to string
        if isinstance(user_id, uuid.UUID):
            return str(user_id)
        
        # If it's a string, validate it as a UUID
        uuid_obj = uuid.UUID(str(user_id))
        return str(uuid_obj)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"Invalid user_id format: {user_id}. Error: {e}")

def convert_to_ist(dt: Union[datetime, str], input_format: Optional[str] = None) -> datetime:
    """
    Converts a datetime object or string to Indian Standard Time (IST).
    
    Args:
        dt: A datetime object or string representing a date and time
        input_format: Format string for parsing dt if it's a string (e.g., '%Y-%m-%d %H:%M:%S')
        
    Returns:
        A datetime object in IST timezone
        
    Examples:
        >>> convert_to_ist(datetime(2023, 1, 1, 12, 0, 0))  # UTC datetime
        datetime(2023, 1, 1, 17, 30, 0, tzinfo=<DstTzInfo 'Asia/Kolkata' IST+5:30:00 STD>)
        >>> convert_to_ist("2023-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")
        datetime(2023, 1, 1, 17, 30, 0, tzinfo=<DstTzInfo 'Asia/Kolkata' IST+5:30:00 STD>)
    """
    if isinstance(dt, str):
        if not input_format:
            # Try common formats
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    dt = datetime.strptime(dt, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Could not parse datetime string: {dt}")
        else:
            dt = datetime.strptime(dt, input_format)
    
    # If datetime has no timezone info, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # Convert to IST
    return dt.astimezone(IST)

def format_datetime_for_google_calendar(dt: Union[datetime, None] = None, date_str: Optional[str] = None, time_str: Optional[str] = None) -> str:
    """
    Formats a datetime for Google Calendar API in ISO format with IST timezone.
    
    Args:
        dt: A datetime object or None if using date_str and time_str
        date_str: Date string in YYYY-MM-DD format (used if dt is None)
        time_str: Time string in HH:MM:SS format (used if dt is None)
        
    Returns:
        An ISO formatted datetime string with IST timezone
        
    Examples:
        >>> format_datetime_for_google_calendar(datetime(2023, 1, 1, 12, 0, 0))
        '2023-01-01T12:00:00+05:30'
        >>> format_datetime_for_google_calendar(None, "2023-01-01", "12:00:00")
        '2023-01-01T12:00:00+05:30'
    """
    if dt is None:
        if date_str and time_str:
            # Ensure time is in HH:MM:SS format
            time_str = format_time_for_db(time_str)
            # Combine date and time strings
            dt_str = f"{date_str} {time_str}"
            # Parse the combined string
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            # Localize to IST
            dt = IST.localize(dt)
        else:
            raise ValueError("Either dt or both date_str and time_str must be provided")
    elif dt.tzinfo is None:
        # If datetime has no timezone, assume it's in IST
        dt = IST.localize(dt)
    else:
        # If datetime has a different timezone, convert to IST
        dt = dt.astimezone(IST)
    
    # Return ISO formatted string
    return dt.isoformat()