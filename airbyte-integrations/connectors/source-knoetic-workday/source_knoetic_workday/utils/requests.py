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
    ) -> str:
        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE_NUMBER" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PAGE_NUMBER", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PER_PAGE", str(per_page))

        header_content: str = self.header_template % (f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (header_content, specific_xml_content)

        return full_xml

    @staticmethod
    def parse_response(response: requests.Response) -> list:

        if response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Request failed with status code {response.status_code}.")

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

        response_data = root.find(".//wd:Response_Data", namespaces)

        workers: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return workers

        for worker in response_data.findall("wd:Worker", namespaces):
            worker_descriptor_elem = worker.find("wd:Worker_Descriptor", namespaces)
            worker_descriptor = worker_descriptor_elem.text if worker_descriptor_elem is not None else None

            worker_data: Dict[str, Union[str | None, List[Dict[str, str]]]] = {
                "Worker_Descriptor": worker_descriptor,
                "Worker_Reference": [],
            }
            for id_elem in worker.findall(".//wd:Worker_Reference/wd:ID", namespaces):
                if id_elem is not None:
                    worker_data["Worker_Reference"].append(
                        {
                            "type": id_elem.attrib.get("wd:type", "Unknown Type"),
                            "value": id_elem.text if id_elem.text is not None else "Unknown ID",
                        }
                    )
            workers.append(worker_data)

        return workers
