from app.soap_util import send_soap_message, parse_soap_response, \
    ParamString, ParamInt, ComplexType, ArrayType
from collections import namedtuple


DrivingSchoolInfo = namedtuple('DrivingSchoolInfo',
                               ['id', 'name', 'web_service_url',
                                ])
LoginInfo = namedtuple('LoginInfo', ['session_id', 'student_id'])

CourseInfo = namedtuple('CourseInfo', ['id', 'type_name', 'category'])

AgendaItem = namedtuple('AgendaItem', ['id', 'name', 'instructor',
                                       'start_time', 'stop_time',
                                       'comment', 'course_info'])

Address = namedtuple('Address', ['street', 'housenumber', 'zipcode', 'city'])


def get_driving_school_info(soap_endpoint: str, handle: str):
    response = send_soap_message(
        soap_endpoint, "Rijschool/Info", "WS_Rijschool_Info",
        "Rijschool_Info_Request", [
            ParamString("Handle", handle),
            ParamInt("studentId", 0)])

    return_values = parse_soap_response(
        soap_endpoint, response, "Rijschool_Info_Response",
        ["Id", "Naam", "WebServiceURL"])

    return DrivingSchoolInfo(id=return_values['Id'],
                             name=return_values['Naam'],
                             web_service_url=return_values['WebServiceURL'])


def student_login(driving_school_info: DrivingSchoolInfo,
                  username: str, password: str):
    response = send_soap_message(
        driving_school_info.web_service_url,
        "Rijschool/Login_Leerling", "WS_Rijschool_Login_Leerling",
        "Rijschool_Login_Leerling_Request", [
            ParamInt("RijschoolId", driving_school_info.id),
            ParamString("Username", username),
            ParamString("Password", password),
            ParamString("RemoteIp", "android")])

    return_values = parse_soap_response(
        driving_school_info.web_service_url, response,
        "Rijschool_Login_Leerling_Response", ["SessionId",
                                              ComplexType("Leerling", ["Id"])])

    return LoginInfo(session_id=return_values['SessionId'],
                     student_id=return_values['Leerling']['Id'])


def get_student_planned_courses(driving_school_info: DrivingSchoolInfo,
                                login_info: LoginInfo):

    response = send_soap_message(
        driving_school_info.web_service_url,
        "Leerling/GetCursussen",
        "WS_Leerlingen_GetCursussen", "Leerlingen_GetCursussen_Request", [
                    ParamInt("RijschoolId", driving_school_info.id),
                    ParamString("SessionId", login_info.session_id),
                    ParamInt("LeerlingId", login_info.student_id),
                    ParamInt("FinishedCourses", 1)
        ])

    courses = parse_soap_response(
        driving_school_info.web_service_url, response,
        "Leerling_GetCursussen_Response", [
            ArrayType("Cursussen", ComplexType("item", [
                "Id", "PakketNaam", "Category"]))
        ])

    items = []
    for course in courses['Cursussen']:

        response = send_soap_message(
            driving_school_info.web_service_url, "Rijschool/Overzicht",
            "WS_Cursus_Overzicht", "Cursus_Overzicht_Request", [
                ParamInt("RijschoolId", driving_school_info.id),
                ParamString("SessionId", login_info.session_id),
                ParamInt("CursusId", course['Id'])
            ])

        agenda_items = parse_soap_response(
            driving_school_info.web_service_url,
            response, "Cursus_Overzicht_Response",
            [ArrayType("Items",
                       ComplexType("item", [
                           "Id",
                           ComplexType("ItemType", ["Naam"]),
                           ComplexType("Instructeur", ["Naam"]),
                           "Start", "Stop", "Opmerkingen"]))])

        course_info = CourseInfo(id=course['Id'],
                                 type_name=course['PakketNaam'],
                                 category=course['Category'])
        for agenda_item in agenda_items['Items']:
            item_info = AgendaItem(
                id=agenda_item['Id'],
                name=agenda_item['ItemType']['Naam'],
                instructor=agenda_item['Instructeur']['Naam'],
                start_time=agenda_item['Start'],
                stop_time=agenda_item['Stop'],
                comment=agenda_item['Opmerkingen'],
                course_info=course_info)

            items.append(item_info)

    return items


def get_driving_school_address(driving_school_info: DrivingSchoolInfo,
                               login_info: LoginInfo) -> Address:

    response = send_soap_message(
        driving_school_info.web_service_url,
        "Rijschool/Info", "WS_Rijschool_NAW", "Rijschool_NAW_Request", [
            ParamInt("RijschoolId", driving_school_info.id),
            ParamString("SessionId", login_info.session_id),
            ParamInt("studentId", login_info.student_id)
        ])

    return_values = parse_soap_response(
        driving_school_info.web_service_url, response,
        "Rijschool_NAW_Response", [
            "Straatnaam", "Huisnummer", "Toevoeging",
            "Postcode", "Plaats"])

    return Address(street=return_values["Straatnaam"],
                   housenumber=(return_values["Huisnummer"] +
                                return_values["Toevoeging"]),
                   zipcode=return_values["Postcode"],
                   city=return_values["Plaats"])
