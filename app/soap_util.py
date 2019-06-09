from typing import Any, Dict, Union, List
from enum import Enum
from io import BytesIO

import requests
from lxml import etree
import dateutil.parser as dateparser

SCHEMA_SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SCHEMA_XSD = "http://www.w3.org/2001/XMLSchema"
SCHEMA_XSI = "http://www.w3.org/2001/XMLSchema-instance"

NAMESPACE_MAP = {
    'soapenv': SCHEMA_SOAP_ENV,
    'xsd': SCHEMA_XSD,
    'xsi': SCHEMA_XSI,
}


class XsdType(Enum):
    STRING = "string"
    INT = "int"


class RequestParameter:
    def __init__(self, name: str, value: Any, type: XsdType):
        self.name = name
        self.value = value
        self.type = type


class ParamString(RequestParameter):
    def __init__(self, name: str, value: str):
        super().__init__(name, value, XsdType.STRING)


class ParamInt(RequestParameter):
    def __init__(self, name: str, value: int):
        super().__init__(name, value, XsdType.INT)


class ComplexType:
    def __init__(self, name: str,
                 values: List[Union[str, List, 'ComplexType']]):
        self.name = name
        self.values = values


class ArrayType:
    def __init__(self, name: str, item_type: ComplexType):
        self.name = name
        self.item_type = item_type


def _create_nsmap(wsdl: str) -> Dict[str, str]:
    nsmap = dict(NAMESPACE_MAP)
    nsmap['tns'] = wsdl
    return nsmap


def _create_soap_message(wsdl: str, operation: str, request_type: str,
                        request_parameters: List[RequestParameter]) -> bytes:

    nsmap = _create_nsmap(wsdl)

    envelope = etree.Element(etree.QName(SCHEMA_SOAP_ENV, 'Envelope'),
                             nsmap=nsmap )

    xsi_type = etree.QName(SCHEMA_XSI, 'type')
    request_type_val = etree.QName(wsdl, request_type)

    body = etree.SubElement(envelope, etree.QName(SCHEMA_SOAP_ENV, 'Body'))
    operation = etree.SubElement(body, etree.QName(wsdl, operation))
    request = etree.SubElement(operation, etree.QName(wsdl, 'request'))
    request.set(xsi_type, request_type_val)

    for param in request_parameters:
        param_tag = etree.QName(wsdl, param.name)
        param_elem = etree.SubElement(request, param_tag)
        param_elem.set(xsi_type, etree.QName(SCHEMA_XSD, param.type.value))
        param_elem.text = str(param.value)

    return etree.tostring(envelope, encoding='utf-8', xml_declaration=True)


def _retrieve_response_elems(
        parent_elem: etree.Element,
        retrieve_response_elems: List[Union[str, ArrayType, ComplexType]]) \
        -> Dict[str, Any]:

    result = {}
    for response_elem in retrieve_response_elems:

        if isinstance(response_elem, ComplexType):
            elem = parent_elem.find(response_elem.name)
            values = _retrieve_response_elems(elem, response_elem.values)
            result[response_elem.name] = values

        elif isinstance(response_elem, ArrayType):
            elem = parent_elem.find(response_elem.name)
            elem_type = elem.attrib[f'{{{SCHEMA_XSI}}}type']
            assert(elem_type.endswith(':Array'))

            items = elem.findall('item')

            item_results = []
            for item in items:
                item_values = _retrieve_response_elems(
                    item, response_elem.item_type.values)
                item_results.append(item_values)

            result[response_elem.name] = item_results

        else:
            elem = parent_elem.find(response_elem)

            elem_type = elem.attrib[f'{{{SCHEMA_XSI}}}type']
            elem_val = elem.text

            if elem_type == 'xsd:int':
                elem_val = int(elem_val)
            elif elem_type == "xsd:dateTime":
                elem_val = dateparser.parse(elem_val)
            elif elem_type != 'xsd:string':
                raise Exception(f"Unknown type: {elem_type}")

            result[response_elem] = elem_val

    return result


def parse_soap_response(
        wsdl: str, response: etree.ElementTree, response_type: str,
        retrieve_response_elems: List[Union[str, ArrayType, ComplexType]]) \
        -> Dict[str, Any]:

    nsmap = _create_nsmap(wsdl)

    return_elem = response.xpath(
        f"//return[@xsi:type='tns:{response_type}']", namespaces=nsmap)

    if not return_elem:
        raise Exception(
            f"There exists no return element with type '{response_type}'")

    return _retrieve_response_elems(return_elem[0], retrieve_response_elems)


def send_soap_message(wsdl: str, soap_action: str, operation: str,
                      request_type: str,
                      request_parameters: [RequestParameter]) -> str:

    msg = _create_soap_message(wsdl, operation,
                               request_type, request_parameters)

    result = requests.post(wsdl, msg, headers={
        'Content-Type': 'text/xml; charset=UTF-8',
        'SOAPAction': soap_action,
        'Accept-Encoding': 'identity'
    })

    if not result.ok:
        raise Exception(f"Operation {operation} returned "
                        f"status code {result.status_code}: {result.text}")

    return etree.parse(BytesIO(result.content))
