import os
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional, Union

import csv
import requests

CURRENT_DIR: str = os.path.dirname(os.path.realpath(__file__))
XML_DIR: str = CURRENT_DIR.replace("utils", "xml")


class WorkdayRequest:
    def __init__(self, base_path: str = XML_DIR) -> None:
        self.base_path: str = base_path
        self.base_template: str = self.read_xml_file("base.xml")
        self.header_template: str = self.read_xml_file("header.xml")

        self.stream_mappings: Dict[str, Dict[str, Union[str, Callable]]] = {
            "workers": {
                "request_file": "workers.xml",
                "parse_response": self.parse_workers_response,
            },
            "organization_hierarchies": {
                "request_file": "organization_hierarchies.xml",
                "parse_response": self.parse_organization_hierarchies_response,
            },
            "ethnicities": {
                "request_file": "ethnicities.xml",
                "parse_response": self.parse_ethnicities_response,
            },
            "gender_identities": {
                "request_file": "gender_identities.xml",
                "parse_response": self.parse_gender_identities_response,
            },
            "locations": {
                "request_file": "locations.xml",
                "parse_response": self.parse_locations_response,
            },
            "job_profiles": {
                "request_file": "job_profiles.xml",
                "parse_response": self.parse_job_profiles_response,
            },
            "positions": {
                "request_file": "positions.xml",
                "parse_response": self.parse_positions_response,
            },
            "sexual_orientations": {
                "request_file": "sexual_orientations.xml",
                "parse_response": self.parse_sexual_orientations_response,
            },
            "references": {
                "request_file": "references.xml",
                "parse_response": self.parse_references_response,
            },
            "base_snapshot_report": {
                "parse_response": self.parse_base_snapshot_report_response,
            },
            "base_historical_report_compensation": {
                "parse_response": self.parse_base_historical_report_compensation_response,
            },
            "base_historical_report_job": {
                "parse_response": self.parse_base_historical_report_job_response,
            },
        }

    def read_xml_file(self, filename: str) -> str:
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()
    
    def get_namespaces(self, element: ET.Element) -> Dict[str, str]:
        """
        Extracts namespaces from the XML element.
        """
        namespaces = {}
        for ns in element.iter():
            if ns.tag.startswith("{"):
                uri, tag = ns.tag[1:].split("}")
                namespaces[uri] = uri
        return {"wd": list(namespaces.keys())[0]}
    
    def safe_find_text(self, element: ET.Element, tag: str, namespaces: Dict[str, str]) -> Optional[str]:
        """
        Safely find the text of a tag in an element.
        """
        if element is None or element.find(tag, namespaces) is None:
            return None
        
        return element.find(tag, namespaces).text 

    def construct_request_body(
        self,
        file_name: str,
        tenant: str,
        username: str,
        password: str,
        page: int,
        per_page: int = 200
    ) -> str:
        specific_xml_content: str = self.read_xml_file(file_name)
        if "PAGE_NUMBER" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PAGE_NUMBER", str(page))
        if "PER_PAGE" in specific_xml_content:
            specific_xml_content = specific_xml_content.replace("PER_PAGE", str(per_page))

        header_content: str = self.header_template % (f"{username}@{tenant}", password)
        full_xml: str = self.base_template % (header_content, specific_xml_content)

        return full_xml

    def parse_response(self, response: requests.Response, stream_name) -> list:
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Request failed with status code {response.status_code}.")

        try:
            xml_data = response.text
            root = ET.fromstring(xml_data)

            namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

            response_data = root.find(".//{urn:com.workday/bsvc}Response_Data", namespaces)

            custom_parse_response_function = self.stream_mappings[stream_name].get("parse_response")
            return custom_parse_response_function(response_data, namespaces)

        except:
            custom_parse_response_function = self.stream_mappings[stream_name].get("parse_response")
            return custom_parse_response_function(response)

    def parse_workers_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        workers: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return workers

        for worker in response_data.findall("{urn:com.workday/bsvc}Worker", namespaces):
            worker_descriptor_elem = worker.find("{urn:com.workday/bsvc}Worker_Descriptor", namespaces)
            worker_descriptor = worker_descriptor_elem.text if worker_descriptor_elem is not None else None

            worker_data: Dict[str, Union[str | None, List[Dict[str, str]]]] = {
                "Worker_Descriptor": worker_descriptor,
                "Worker_Reference": [],
            }
            for id_elem in worker.findall(
                ".//{urn:com.workday/bsvc}Worker_Reference/{urn:com.workday/bsvc}ID", namespaces
            ):
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
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        organization_hierarchies: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return organization_hierarchies

        for org in response_data.findall("{urn:com.workday/bsvc}Organization", namespaces):
            org_reference_elem = org.find("{urn:com.workday/bsvc}Organization_Reference", namespaces)
            org_data_elem = org.find("{urn:com.workday/bsvc}Organization_Data", namespaces)

            org_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in org_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            org_data = {
                "Reference_ID": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Reference_ID", namespaces),
                "Name": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Name", namespaces),
                "Availibility_Date": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Availibility_Date", namespaces),
                "Last_Updated_DateTime": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces),
                "Inactive": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces),
                "Include_Manager_in_Name": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces),
                "Include_Organization_Code_in_Name": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces),
                "Organization_Type_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Type_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Type_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "Organization_Subtype_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Subtype_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "Organization_Visibility_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}Organization_Visibility_Reference", namespaces)
                        is not None
                        else []
                    )
                },
                "External_IDs_Data": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-System_ID": id_elem.attrib.get(
                                    "{urn:com.workday/bsvc}System_ID", "Unknown System ID"
                                ),
                            }
                            for id_elem in org_data_elem.find(
                                "{urn:com.workday/bsvc}External_IDs_Data", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if org_data_elem.find("{urn:com.workday/bsvc}External_IDs_Data", namespaces) is not None
                        else []
                    )
                },
                "Hierarchy_Data": {
                    "Top-Level_Organization_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in org_data_elem.find(
                                    "{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference",
                                    namespaces,
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if org_data_elem.find(
                                "{urn:com.workday/bsvc}Hierarchy_Data/{urn:com.workday/bsvc}Top-Level_Organization_Reference",
                                namespaces,
                            )
                            is not None
                            else []
                        )
                    }
                },
            }

            organization_hierarchies.append(
                {
                    "Organization_Reference": org_reference,
                    "Organization_Data": org_data,
                }
            )

        return organization_hierarchies

    def parse_ethnicities_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        ethnicities: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return ethnicities

        for ethnicity in response_data.findall("{urn:com.workday/bsvc}Ethnicity", namespaces):
            ethnicity_reference_elem = ethnicity.find("{urn:com.workday/bsvc}Ethnicity_Reference", namespaces)
            ethnicity_data_elem = ethnicity.find("{urn:com.workday/bsvc}Ethnicity_Data", namespaces)

            ethnicity_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_data_elem.find("{urn:com.workday/bsvc}Location_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if ethnicity_data_elem.find("{urn:com.workday/bsvc}Location_Reference", namespaces) is not None else []
            }

            ethnicity_mapping_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in ethnicity_data_elem.find("{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if ethnicity_data_elem.find("{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces) is not None else []
            }

            ethnicity_data = {
                "ID": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                "Name": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}Name", namespaces),
                "Description": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}Description", namespaces),
                "Location_Reference": location_reference,
                "Ethnicity_Mapping_Reference": ethnicity_mapping_reference,
                "Inactive": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces)
            }

            ethnicities.append({
                "Ethnicity_Reference": ethnicity_reference,
                "Ethnicity_Data": ethnicity_data
            })

        return ethnicities
    
    def parse_gender_identities_response(
    self,
    response_data: ET.Element,
    namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        gender_identities: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return gender_identities

        for gender_identity in response_data.findall("{urn:com.workday/bsvc}Gender_Identity", namespaces):
            gender_identity_reference_elem = gender_identity.find("{urn:com.workday/bsvc}Gender_Identity_Reference", namespaces)
            gender_identity_data_elem = gender_identity.find("{urn:com.workday/bsvc}Gender_Identity_Data", namespaces)

            gender_identity_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in gender_identity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            gender_identity_data = {
                "ID": self.safe_find_text(gender_identity_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                "Gender_Identity_Name": self.safe_find_text(gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Name", namespaces),
                "Gender_Identity_Code": self.safe_find_text(gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Code", namespaces),
                "Gender_Identity_Inactive": self.safe_find_text(gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Inactive", namespaces)
            }

            gender_identities.append({
                "Gender_Identity_Reference": gender_identity_reference,
                "Gender_Identity_Data": gender_identity_data
            })

        return gender_identities

    def parse_locations_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        locations: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return locations

        for location in response_data.findall("{urn:com.workday/bsvc}Location", namespaces):
            location_reference_elem = location.find("{urn:com.workday/bsvc}Location_Reference", namespaces)
            location_data_elem = location.find("{urn:com.workday/bsvc}Location_Data", namespaces)

            location_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_usage_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Usage_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Usage_Reference", namespaces) is not None else []
            }

            location_type_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Type_Reference", namespaces) is not None else []
            }

            location_hierarchy_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces) is not None else []
            }

            time_profile_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Time_Profile_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Time_Profile_Reference", namespaces) is not None else []
            }

            integration_id_data = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-System_ID": id_elem.attrib.get("{urn:com.workday/bsvc}System_ID", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Integration_ID_Data", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Integration_ID_Data", namespaces) is not None else []
            }

            locale_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Locale_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Locale_Reference", namespaces) is not None else []
            }

            time_zone_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Time_Zone_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Time_Zone_Reference", namespaces) is not None else []
            }

            default_currency_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in location_data_elem.find("{urn:com.workday/bsvc}Default_Currency_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if location_data_elem.find("{urn:com.workday/bsvc}Default_Currency_Reference", namespaces) is not None else []
            }

            contact_data_elem = location_data_elem.find("{urn:com.workday/bsvc}Contact_Data", namespaces)
            address_data_elem = contact_data_elem.find("{urn:com.workday/bsvc}Address_Data", namespaces) if contact_data_elem is not None else None
            address_data = {
                "-Address_Format_Type": address_data_elem.attrib.get("{urn:com.workday/bsvc}Address_Format_Type"),
                "-Defaulted_Business_Site_Address": address_data_elem.attrib.get("{urn:com.workday/bsvc}Defaulted_Business_Site_Address"),
                "-Effective_Date": address_data_elem.attrib.get("{urn:com.workday/bsvc}Effective_Date"),
                "-Formatted_Address": address_data_elem.attrib.get("{urn:com.workday/bsvc}Formatted_Address"),
                "Address_ID": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Address_ID", namespaces),
                "Address_Line_Data": {
                    "#content": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Address_Line_Data", namespaces),
                    "-Descriptor": address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Descriptor"),
                    "-Type": address_data_elem.find("{urn:com.workday/bsvc}Address_Line_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Type")
                },
                "Address_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Address_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Address_Reference", namespaces) is not None else []
                },
                "Country_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces) is not None else []
                },
                "Country_Region_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Reference", namespaces) is not None else []
                },
                "Country_Region_Descriptor": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Country_Region_Descriptor", namespaces),
                "Last_Modified": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Last_Modified", namespaces),
                "Municipality": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Municipality", namespaces),
                "Number_of_Days": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Number_of_Days", namespaces),
                "Postal_Code": self.safe_find_text(address_data_elem, "{urn:com.workday/bsvc}Postal_Code", namespaces),
                "Usage_Data": {
                    "-Public": address_data_elem.find("{urn:com.workday/bsvc}Usage_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Public"),
                    "Type_Data": {
                        "-Primary": address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data", namespaces).attrib.get("{urn:com.workday/bsvc}Primary"),
                        "Type_Reference": {
                            "ID": [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                                }
                                for id_elem in address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ] if address_data_elem.find("{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference", namespaces) is not None else []
                        }
                    }
                }
            } if address_data_elem is not None else None

            contact_data = {
                "Address_Data": address_data
            }

            location_data = {
                "Location_ID": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Location_ID", namespaces),
                "Location_Name": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Location_Name", namespaces),
                "Location_Usage_Reference": location_usage_reference,
                "Location_Type_Reference": location_type_reference,
                "Location_Hierarchy_Reference": location_hierarchy_reference,
                "Integration_ID_Data": integration_id_data,
                "Inactive": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces),
                "Latitude": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Latitude", namespaces),
                "Longitude": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Longitude", namespaces),
                "Altitude": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Altitude", namespaces),
                "Time_Profile_Reference": time_profile_reference,
                "Locale_Reference": locale_reference,
                "Time_Zone_Reference": time_zone_reference,
                "Default_Currency_Reference": default_currency_reference,
                "Contact_Data": contact_data,
            }

            locations.append({
                "Location_Reference": location_reference,
                "Location_Data": location_data
            })

        return locations


    def parse_job_profiles_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        job_profiles: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return job_profiles

        for job_profile in response_data.findall("{urn:com.workday/bsvc}Job_Profile", namespaces):
            job_profile_reference_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Reference", namespaces)
            job_profile_data_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Data", namespaces)

            job_profile_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                    }
                    for id_elem in job_profile_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ] if job_profile_reference_elem is not None else []
            }

            job_profile_basic_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Basic_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_pay_rate_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Pay_Rate_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_exempt_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Exempt_Data", namespaces) if job_profile_data_elem is not None else None
            job_profile_compensation_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Compensation_Data", namespaces) if job_profile_data_elem is not None else None
            job_classification_data_elems = job_profile_data_elem.findall("{urn:com.workday/bsvc}Job_Classification_Data", namespaces) if job_profile_data_elem is not None else []
            workers_compensation_code_replacement_data_elem = job_profile_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Replacement_Data", namespaces) if job_profile_data_elem is not None else None
            
            job_profile_basic_data = {}

            if job_profile_basic_data_elem is not None:
                job_profile_basic_data["Job_Title"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Job_Title", namespaces)
                job_profile_basic_data["Inactive"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces)
                job_profile_basic_data["Include_Job_Code_in_Name"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Include_Job_Code_in_Name", namespaces)
                job_profile_basic_data["Work_Shift_Required"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Work_Shift_Required", namespaces)
                job_profile_basic_data["Public_Job"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Public_Job", namespaces)
                job_profile_basic_data["Critical_Job"] = self.safe_find_text(job_profile_basic_data_elem, "{urn:com.workday/bsvc}Critical_Job", namespaces)

                job_family_data_elem = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Family_Data", namespaces)
                job_family_data = {
                    "Job_Family_Reference": {
                        "ID": [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                            }
                            for id_elem in job_family_data_elem.find("{urn:com.workday/bsvc}Job_Family_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ] if job_family_data_elem.find("{urn:com.workday/bsvc}Job_Family_Reference", namespaces) is not None else []
                    }
                } if job_family_data_elem is not None else None

                job_level_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Level_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Level_Reference", namespaces) is not None else []
                }

                management_level_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Management_Level_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Management_Level_Reference", namespaces) is not None else []
                }

                referral_payment_plan_reference = {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces) is not None else []
                }

                job_profile_basic_data["Job_Family_Data"] = job_family_data
                job_profile_basic_data["Job_Level_Reference"] = job_level_reference
                job_profile_basic_data["Management_Level_Reference"] = management_level_reference
                job_profile_basic_data["Referral_Payment_Plan_Reference"] = referral_payment_plan_reference

                job_description = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Description", namespaces) 
                if job_description is not None:
                    job_profile_basic_data["Job_Description"] = job_description.text

            job_profile_pay_rate_data = {
                "Country_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_pay_rate_data_elem is not None and job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces) is not None else []
                },
                "Pay_Rate_Type_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_pay_rate_data_elem is not None and job_profile_pay_rate_data_elem.find("{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces) is not None else []
                }
            } if job_profile_pay_rate_data_elem is not None else None
            
            workers_compensation_code_replacement_data = {
                "Workers_Compensation_Code_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in workers_compensation_code_replacement_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if workers_compensation_code_replacement_data_elem.find("{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces) is not None else []
                }
            } if workers_compensation_code_replacement_data_elem is not None else None

            job_profile_exempt_data = {
                "Location_Context_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_exempt_data_elem.find("{urn:com.workday/bsvc}Location_Context_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_exempt_data_elem is not None and job_profile_exempt_data_elem.find("{urn:com.workday/bsvc}Location_Context_Reference", namespaces) is not None else []
                },
                "Job_Exempt": self.safe_find_text(job_profile_exempt_data_elem, "{urn:com.workday/bsvc}Job_Exempt", namespaces)
            } if job_profile_exempt_data_elem is not None else None

            job_profile_compensation_data = {
                "Compensation_Grade_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                        }
                        for id_elem in job_profile_compensation_data_elem.find("{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ] if job_profile_compensation_data_elem is not None and job_profile_compensation_data_elem.find("{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces) is not None else []
                }
            } if job_profile_compensation_data_elem is not None else None

            job_classifications_data = [
                {
                    "Job_Classifications_Reference": {
                        "ID": [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type")
                            }
                            for id_elem in job_classification_data_elem.find("{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ] if job_classification_data_elem.find("{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces) is not None else []
                    }
                } for job_classification_data_elem in job_classification_data_elems
            ]

            job_profile_data = {
                "Job_Code": self.safe_find_text(job_profile_data_elem, "{urn:com.workday/bsvc}Job_Code", namespaces),
                "Effective_Date": self.safe_find_text(job_profile_data_elem, "{urn:com.workday/bsvc}Effective_Date", namespaces),
                "Job_Profile_Basic_Data": job_profile_basic_data,
                "Job_Profile_Pay_Rate_Data": job_profile_pay_rate_data,
                "Workers_Compensation_Code_Replacement_Data": workers_compensation_code_replacement_data,
                "Job_Profile_Exempt_Data": job_profile_exempt_data,
                "Job_Profile_Compensation_Data": job_profile_compensation_data,
                "Job_Classification_Data": job_classifications_data,
            }

            job_profiles.append({
                "Job_Profile_Reference": job_profile_reference,
                "Job_Profile_Data": job_profile_data
            })

        return job_profiles


    def parse_positions_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        positions: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return positions

        for position in response_data.findall("{urn:com.workday/bsvc}Position", namespaces):
            position_reference_elem = position.find("{urn:com.workday/bsvc}Position_Reference", namespaces)
            position_data_elem = position.find("{urn:com.workday/bsvc}Position_Data", namespaces)

            position_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in position_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            } if position_reference_elem is not None else None

            position_definition_data_elem = position_data_elem.find("{urn:com.workday/bsvc}Position_Definition_Data", namespaces) if position_data_elem is not None else None

            position_definition_data = {
                "Position_ID": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Position_ID", namespaces),
                "Job_Posting_Title": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Job_Posting_Title", namespaces),
                "Academic_Tenure_Eligible": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Academic_Tenure_Eligible", namespaces),
                "Available_For_Hire": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Available_For_Hire", namespaces),
                "Available_for_Recruiting": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Available_for_Recruiting", namespaces),
                "Hiring_Freeze": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Hiring_Freeze", namespaces),
                "Work_Shift_Required": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Work_Shift_Required", namespaces),
                "Available_for_Overlap": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Available_for_Overlap", namespaces),
                "Critical_Job": self.safe_find_text(position_definition_data_elem, "{urn:com.workday/bsvc}Critical_Job", namespaces),
            }
            
            position_status_reference = [
                {
                    "ID": {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                } for id_elem in position_definition_data_elem.findall("{urn:com.workday/bsvc}Position_Status_Reference/{urn:com.workday/bsvc}ID", namespaces)
            ]
            position_definition_data["Position_Status_Reference"] = position_status_reference

            position_data = {
                "Supervisory_Organization_Reference": {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in position_data_elem.findall("{urn:com.workday/bsvc}Supervisory_Organization_Reference/{urn:com.workday/bsvc}ID", namespaces)
                    ] if position_data_elem is not None else []
                },
                "Effective_Date": self.safe_find_text(position_data_elem, "{urn:com.workday/bsvc}Effective_Date", namespaces),
                "Position_Definition_Data": position_definition_data,
                "Closed": self.safe_find_text(position_data_elem, "{urn:com.workday/bsvc}Closed", namespaces),
            }

            positions.append({
                "Position_Reference": position_reference,
                "Position_Data": position_data
            })

        return positions
    
    def parse_sexual_orientations_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        sexual_orientations: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return sexual_orientations

        for orientation in response_data.findall("{urn:com.workday/bsvc}Sexual_Orientation", namespaces):
            orientation_reference_elem = orientation.find("{urn:com.workday/bsvc}Sexual_Orientation_Reference", namespaces)
            orientation_data_elem = orientation.find("{urn:com.workday/bsvc}Sexual_Orientation_Data", namespaces)

            orientation_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in orientation_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            } if orientation_reference_elem is not None else None

            orientation_data = {}
            if orientation_data_elem is not None:
                orientation_data["ID"] = self.safe_find_text(orientation_data_elem, "{urn:com.workday/bsvc}ID", namespaces)
                orientation_data["Sexual_Orientation_Name"] = self.safe_find_text(orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Name", namespaces)
                orientation_data["Sexual_Orientation_Code"] = self.safe_find_text(orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Code", namespaces)
                orientation_data["Sexual_Orientation_Description"] = self.safe_find_text(orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Description", namespaces)
                orientation_data["Sexual_Orientation_Inactive"] = self.safe_find_text(orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Inactive", namespaces)

            sexual_orientations.append({
                "Sexual_Orientation_Reference": orientation_reference,
                "Sexual_Orientation_Data": orientation_data
            })

        return sexual_orientations

    def parse_references_response(
        self,
        response_data: ET.Element,
        namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        references: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return references

        for reference in response_data.findall("{urn:com.workday/bsvc}Reference_ID", namespaces):
            reference_descriptor = reference.attrib.get("{urn:com.workday/bsvc}Descriptor")
            reference_id_reference_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Reference", namespaces)
            reference_id_data_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Data", namespaces)

            reference_id_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in reference_id_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            } if reference_id_reference_elem is not None else None

            reference_id_data = {
                "ID": self.safe_find_text(reference_id_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                "Reference_ID_Type": self.safe_find_text(reference_id_data_elem, "{urn:com.workday/bsvc}Reference_ID_Type", namespaces),
                "Referenced_Object_Descriptor": self.safe_find_text(reference_id_data_elem, "{urn:com.workday/bsvc}Referenced_Object_Descriptor", namespaces)
            } if reference_id_data_elem is not None else None

            references.append({
                "-Descriptor": reference_descriptor,
                "Reference_ID_Reference": reference_id_reference,
                "Reference_ID_Data": reference_id_data
            })

        return references

    def parse_base_snapshot_report_response(
        self,
        response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        response_csv = response.content.decode("utf-8")
        reader = csv.DictReader(response_csv.splitlines())

        return [row for row in reader]

    def parse_base_historical_report_compensation_response(
        self,
        response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        xml_data = response.text
        root = ET.fromstring(xml_data)

        main_compensation_tag = ""
        sub_compensation_tag = ""

        # Tags can vary depending on the way the Workday integration was setup
        if "Compensation_History_-_Previous_System_group" in xml_data and "Compensation_History_Record_from_Previous_System" in xml_data:
            main_compensation_tag = "Compensation_History_-_Previous_System_group"
            sub_compensation_tag = "Compensation_History_Record_from_Previous_System"
        elif "Job_History_from_Previous_System_group" in xml_data and "Job_Position_History_Record_from_Previous_System" in xml_data:
            main_compensation_tag = "Job_History_from_Previous_System_group"
            sub_compensation_tag = "Job_Position_History_Record_from_Previous_System"


        namespaces = self.get_namespaces(root)
        namespace_tag = namespaces["wd"]

        compensation_records: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        for report_entry in root.findall(f".//{{{namespace_tag}}}Report_Entry", namespaces):
            employee_id = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Employee_ID", namespaces)
            worker_elem = report_entry.find(f"{{{namespace_tag}}}Worker", namespaces)
            worker_descriptor = worker_elem.attrib.get(f"{{{namespace_tag}}}Descriptor") if worker_elem is not None else None
            worker_ids = [
                {
                    "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"),
                    "#content": id_elem.text
                }
                for id_elem in worker_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
            ] if worker_elem is not None else []

            compensation_history = []
            for history_elem in report_entry.findall(f"{{{namespace_tag}}}{main_compensation_tag}", namespaces):
                compensation_history_entry_elem = history_elem.find(f"{{{namespace_tag}}}{sub_compensation_tag}", namespaces)
                currency_elem = history_elem.find(f"{{{namespace_tag}}}Currency", namespaces)
                frequency_elem = history_elem.find(f"{{{namespace_tag}}}Frequency", namespaces)

                compensation_history_item = {
                    "Worker_History_Name": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Worker_History_Name", namespaces),
                    "Effective_Date": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Effective_Date", namespaces),
                    "Reason": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Reason", namespaces),
                    "Amount": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount", namespaces),
                    "Amount_Change": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount_Change", namespaces),
                }

                if compensation_history_entry_elem is not None:
                    compensation_history_item[sub_compensation_tag] = {
                        "-Descriptor": compensation_history_entry_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {
                                "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"),
                                "#content": id_elem.text
                            }
                            for id_elem in compensation_history_entry_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                if currency_elem is not None:
                    compensation_history_item["Currency"] = {
                        "-Descriptor": currency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {
                                "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"),
                                "#content": id_elem.text
                            }
                            for id_elem in currency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ]
                    }
                
                if frequency_elem is not None:
                    compensation_history_item["Frequency"] = {
                        "-Descriptor": frequency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {
                                "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"),
                                "#content": id_elem.text
                            }
                            for id_elem in frequency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ]
                    }

                compensation_history.append(compensation_history_item)

            record = {
                "Employee_ID": employee_id,
                "Worker": {
                    "-Descriptor": worker_descriptor,
                    "ID": worker_ids
                }
            }

            if len(compensation_history) > 0:
                record[main_compensation_tag] = compensation_history
            
            compensation_records.append(record)

        print('Compensation Records!!!')
        print(compensation_records)
        return compensation_records


    
    def parse_base_historical_report_job_response(
        self,
        response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        # TODO - @erbzz to implement this

        return []
