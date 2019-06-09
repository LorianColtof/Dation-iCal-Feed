from flask import Flask
from icalendar import Calendar, Event
from datetime import datetime
from pytz import timezone

from app import dation_service

app = Flask(__name__)
app.config.from_object('config.Config')


@app.route('/calendar.ics')
def calendar_ics():
    ds_info = dation_service.get_driving_school_info(
        app.config["SOAP_ENDPOINT"], app.config["SCHOOL_HANDLE"])
    login_info = dation_service.student_login(ds_info,
                                              app.config["USERNAME"],
                                              app.config["PASSWORD"])

    planning = dation_service.get_student_planned_courses(ds_info, login_info)

    ds_address = dation_service.get_driving_school_address(
        ds_info, login_info)

    address = (f"{ds_address.street} {ds_address.housenumber}, "
               f"{ds_address.zipcode} {ds_address.city}")

    tz = timezone("Europe/Amsterdam")

    cal = Calendar()
    cal.add('prodid', '-//Dation ICS feed//loriancoltof.nl//')
    cal.add('version', '2.0')

    for item in planning:
        event = Event()

        event.add('summary', item.name)
        event.add('dtstart', item.start_time.astimezone(tz))
        event.add('dtend', item.stop_time.astimezone(tz))
        event.add('dtstamp', datetime.now())

        event.add('description',
                  f"Instructeur: {item.instructor}\n"
                  f"Pakket: {item.course_info.type_name} "
                  f"({item.course_info.category})")
        event.add('location', address)

        cal.add_component(event)

    return cal.to_ical(), {"Content-Type": "text/calendar"}
