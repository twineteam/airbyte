import json
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union

import requests

CURRENT_DIR: str = os.path.dirname(os.path.realpath(__file__))
XML_DIR: str = CURRENT_DIR.replace("utils", "xml")


class WorkdayRequest:
    def __init__(self, base_path: str = XML_DIR) -> None:
        self.base_path: str = base_path
        self.base_template: str = self.read_xml_file("base.xml")
        self.header_template: str = self.read_xml_file("header.xml")

        self.stream_mappings = {
            "workers": {
                "request_file": "workers.xml",
                "parse_response": self.parse_workers_response,
            },
            "organization_hierarchies": {
                "request_file": "organization_hierarchies.xml",
                "parse_response": self.parse_organization_hierarchies_response,
            }
        }

    def read_xml_file(self, filename: str) -> str:
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()

    def construct_request_body(
        self,
        file_name: str,
        tenant: str,
        username: str,
        password: str,
        page: int,
        per_page: int = 200,
        stream_name: str = None,
    ) -> str:
        # custom request bodies for certain streams
        custom_construct_request_body = self.stream_mappings[stream_name].get(
            "construct_request_body", None)
        if custom_construct_request_body is not None:
            return self.stream_mappings[stream_name]["construct_request_body"](
                file_name, tenant, username, password, page, per_page)

        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE_NUMBER" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace(
                "PAGE_NUMBER", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace(
                "PER_PAGE", str(per_page))

        header_content: str = self.header_template % (
            f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (
            header_content, specific_xml_content)

        return full_xml

    def parse_response(self, response: requests.Response, stream_name) -> list:
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(
                f"Request failed with status code {response.status_code}.")

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = {
            "env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

        response_data = root.find(
            ".//{urn:com.workday/bsvc}Response_Data", namespaces)

        custom_parse_response_function = self.stream_mappings[stream_name].get(
            "parse_response")
        return custom_parse_response_function(response_data, namespaces)

    def parse_workers_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        workers: List[Dict[str,
                           Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return workers

        for worker in response_data.findall("{urn:com.workday/bsvc}Worker", namespaces):
            worker_descriptor_elem = worker.find(
                "{urn:com.workday/bsvc}Worker_Descriptor", namespaces)
            worker_descriptor = worker_descriptor_elem.text if worker_descriptor_elem is not None else None

            worker_data: Dict[str, Union[str | None, List[Dict[str, str]]]] = {
                "Worker_Descriptor": worker_descriptor,
                "Worker_Reference": [],
            }
            for id_elem in worker.findall(".//{urn:com.workday/bsvc}Worker_Reference/{urn:com.workday/bsvc}ID", namespaces):
                if id_elem is not None:
                    worker_data["Worker_Reference"].append(
                        {
                            "type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            "value": id_elem.text if id_elem.text is not None else "Unknown ID",
                        }
                    )
            workers.append(worker_data)

        return workers

    def parse_organization_hierarchies_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        organization_hierarchies: List[Dict[str,
                                            Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return organization_hierarchies

        for org in response_data.findall("{urn:com.workday/bsvc}Organization", namespaces):
            org_reference_elem = org.find(
                "{urn:com.workday/bsvc}Organization_Reference", namespaces)
            org_data_elem = org.find(
                "{urn:com.workday/bsvc}Organization_Data", namespaces)

            org_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in org_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            org_data = {
                "Reference_ID": org_data_elem.find("{urn:com.workday/bsvc}Reference_ID", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Reference_ID", namespaces) is not None else None,
                "Name": org_data_elem.find("{urn:com.workday/bsvc}Name", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Name", namespaces) is not None else None,
                "Availibility_Date": org_data_elem.find("{urn:com.workday/bsvc}Availibility_Date", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Availibility_Date", namespaces) is not None else None,
                "Last_Updated_DateTime": org_data_elem.find("{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces) is not None else None,
                "Inactive": org_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Inactive", namespaces) is not None else None,
                "Include_Manager_in_Name": org_data_elem.find("{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces) is not None else None,
                "Include_Organization_Code_in_Name": org_data_elem.find("{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces).text if org_data_elem.find("{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces) is not None else None,
                "Organization_Type_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in org_data_elem.find("{urn:com.workday/bsvc}Organization_Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if org_data_elem.find("{urn:com.workday/bsvc}Organization_Type_Reference", namespaces) is not None else []
                },
                "Organization_Subtype_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in org_data_elem.find("{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if org_data_elem.find("{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces) is not None else []
                },
                "Organization_Visibility_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in org_data_elem.find("{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if org_data_elem.find("{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces) is not None else []
                },
                "External_IDs_Data": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-System_ID": id_elem.attrib.get("{urn:com.workday/bsvc}System_ID", "Unknown System ID")
                        }
                        for id_elem in org_data_elem.find("{urn:com.workday/bsvc}External_IDs_Data", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if org_data_elem.find("{urn:com.workday/bsvc}External_IDs_Data", namespaces) is not None else []
                },
                "Hierarchy_Data": {
                    "Top-Level_Organization_Reference": {
                        "ID": [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                            }
                            for id_elem in org_data_elem.find("{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ] if org_data_elem.find("{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference", namespaces) is not None else []
                    }
                }
            }

            organization_hierarchies.append({
                "Organization_Reference": org_reference,
                "Organization_Data": org_data,
            })

        return organization_hierarchies
