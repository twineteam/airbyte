import csv
import os
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Optional, Union

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
            "worker_profile": {
                "request_file": "worker_profile.xml",
                "parse_response": self.parse_worker_profile_response,
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

    xmlns = r"{urn:com.workday/bsvc}"

    def read_xml_file(self, filename: str) -> str:
        """
        Reads the contents of an XML file.

        Args:
            filename (str): The name of the file to read.
            
        Returns:
            str: The contents of the file.
        """
        with open(os.path.join(self.base_path, filename), "r") as file:
            return file.read()

    @staticmethod
    def get_namespaces(element: ET.Element) -> Dict[str, str]:
        """
        Extracts the namespaces from an XML element.

        Args:
            element (ET.Element): The XML element to extract namespaces from.

        Returns:
            Dict[str, str]: A dictionary of namespace prefixes and URIs.
        """
        namespaces = {}
        for ns in element.iter():
            if ns.tag.startswith("{"):
                uri, _ = ns.tag[1:].split("}")
                namespaces[uri] = uri
        return {"wd": list(namespaces.keys())[0]}

    @staticmethod
    def safe_find_text(element: ET.Element | None, tag: str, namespaces: Dict[str, str]) -> str | None:
        """
        Safely finds and returns the text content of an XML element.

        Args:
            element (ET.Element | None): The XML element to search within.
            tag (str): The tag name of the element to find.
            namespaces (Dict[str, str]): A dictionary of XML namespace prefixes and URIs.

        Returns:
            str | None: The text content of the found element, or None if the element or tag is not found.

        """
        if element is None:
            return None

        found_element = element.find(tag, namespaces)
        if found_element is None:
            return None

        return found_element.text
    
    @staticmethod
    def safe_get_attrib(element: ET.Element | None, attrib: str) -> str | None:
        """
        Safely finds and returns the value of an XML element attribute.

        Args:
            element (ET.Element | None): The XML element to search within.
            attrib (str): The attribute name to find.

        Returns:
            str | None: The value of the found attribute, or None if the element or attribute is not found.

        """
        if element is None:
            return None

        return element.attrib.get(attrib)
    
    def construct_request_body(
        self, file_name: str, tenant: str, username: str, password: str, page: int, per_page: int = 200
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
        
        custom_parse_response_function = self.stream_mappings[stream_name].get("parse_response")

        try:
            xml_data = response.text
            root = ET.fromstring(xml_data)

            namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}

            response_data = root.find(".//{urn:com.workday/bsvc}Response_Data", namespaces)

            if response_data is None:
                return custom_parse_response_function(response)

            return custom_parse_response_function(response_data, namespaces)

        except Exception as e:
            return custom_parse_response_function(response)

    def parse_workers_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        workers = []

        for worker in response_data.findall(f"{self.xmlns}Worker", namespaces):
            worker_descriptor_elem = worker.find(f"{self.xmlns}Worker_Descriptor", namespaces)
            worker_descriptor = worker_descriptor_elem.text if worker_descriptor_elem is not None else None

            worker_data: Dict[str, str | List[Dict[str, str]] | None] = {
                "Worker_Descriptor": worker_descriptor,
            }

            worker_reference = []
            for id_elem in worker.findall(
                ".//{urn:com.workday/bsvc}Worker_Reference/{urn:com.workday/bsvc}ID", namespaces
            ):
                worker_reference.append(
                    {
                        "type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        "value": id_elem.text if id_elem.text is not None else "Unknown ID",
                    }
                )

            worker_data["Worker_Reference"] = worker_reference
            workers.append(worker_data)

        return workers

    def parse_worker_profile_response(self, response: requests.Response) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        if response.status_code != 200:
            raise requests.exceptions.HTTPError(f"Request failed with status code {response.status_code}.")

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = {"env": "http://schemas.xmlsoap.org/soap/envelope/", "wd": "urn:com.workday/bsvc"}
        namespace_tag = f"{{{namespaces['wd']}}}"

        profile = root.find(f".//wd:Worker_Profile", namespaces)
        if profile is None:
            return None
        
        worker_reference_elem = profile.find(f"{namespace_tag}Worker_Reference", namespaces)
        employee_reference_elem = worker_reference_elem.find(f"{namespace_tag}Employee_Reference", namespaces)
        contingent_worker_reference_elem = worker_reference_elem.find(f"{namespace_tag}Contingent_Worker_Reference", namespaces)

        profile_data = {}
        
        if employee_reference_elem is not None:
            profile_data["Worker_Reference"] = {
                "Employee_Reference": {
                    "Integration_ID_Reference": {
                        "-Descriptor": self.safe_get_attrib(employee_reference_elem.find(f"{namespace_tag}Integration_ID_Reference", namespaces), f"{namespace_tag}Descriptor"),
                        "ID": [
                            {
                                "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                                "#content": id_elem.text
                            }
                            for id_elem in employee_reference_elem.findall(f"{namespace_tag}Integration_ID_Reference/{namespace_tag}ID", namespaces)
                        ]
                    }
                }
            }
        elif contingent_worker_reference_elem is not None:
            profile_data["Worker_Reference"] = {
                "Contingent_Worker_Reference": {
                    "Integration_ID_Reference": {
                        "-Descriptor": self.safe_get_attrib(contingent_worker_reference_elem.find(f"{namespace_tag}Integration_ID_Reference", namespaces), f"{namespace_tag}Descriptor"),
                        "ID": [
                            {
                                "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                                "#content": id_elem.text
                            }
                            for id_elem in contingent_worker_reference_elem.findall(f"{namespace_tag}Integration_ID_Reference/{namespace_tag}ID", namespaces)
                        ]
                    }
                }
            }

        worker_profile_data_elem = profile.find(f"{namespace_tag}Worker_Profile_Data", namespaces)
        worker_profile_data = {}

        worker_status_data_elem = worker_profile_data_elem.find(f"{namespace_tag}Worker_Status_Data", namespaces)

        if worker_status_data_elem is not None:
            worker_status_data = {
                "Active": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Active", namespaces),
                "Hire_Date": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Hire_Date", namespaces),
                "Original_Hire_Date": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Original_Hire_Date", namespaces),
                "Hire_Reason": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Hire_Reason", namespaces),
                "Continuous_Service_Date": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Continuous_Service_Date", namespaces),
                "Retired": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Retired", namespaces),
                "Seniority_Date": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Seniority_Date", namespaces),
                "Days_Unemployed": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Days_Unemployed", namespaces),
                "Months_Continuous_Prior_Employment": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Months_Continuous_Prior_Employment", namespaces),
                "Probation_Status_Data": self.safe_find_text(worker_status_data_elem, f"{namespace_tag}Probation_Status_Data", namespaces),
            }

            termination_status_data_elem = worker_status_data_elem.find(f"{namespace_tag}Termination_Status_Data", namespaces)
            termination_status_data = {
                "Termination_Date": self.safe_find_text(termination_status_data_elem, f"{namespace_tag}Termination_Date", namespaces),
                "Termination_Reason": self.safe_find_text(termination_status_data_elem, f"{namespace_tag}Termination_Reason", namespaces),
                "Termination_Category": self.safe_find_text(termination_status_data_elem, f"{namespace_tag}Termination_Category", namespaces),
                "Involuntary_Termination": self.safe_find_text(termination_status_data_elem, f"{namespace_tag}Involuntary_Termination", namespaces),
                "Terminated": self.safe_find_text(termination_status_data_elem, f"{namespace_tag}Terminated", namespaces),
            } if termination_status_data_elem is not None else None

            worker_status_data["Termination_Status_Data"] = termination_status_data
            worker_profile_data["Worker_Status_Data"] = worker_status_data
        

        worker_personal_data_elem = worker_profile_data_elem.find(f"{namespace_tag}Worker_Personal_Data", namespaces)
        if worker_personal_data_elem is not None:
            biographic_data_elem = worker_personal_data_elem.find(f"{namespace_tag}Biographic_Data", namespaces)
            contact_data_elem = worker_personal_data_elem.find(f"{namespace_tag}Contact_Data", namespaces)
            demographic_data_elem = worker_personal_data_elem.find(f"{namespace_tag}Demographic_Data", namespaces)
            name_data_elem = worker_personal_data_elem.find(f"{namespace_tag}Name_Data", namespaces)

            biographic_data = {
                "Date_Of_Birth": self.safe_find_text(biographic_data_elem, f"{namespace_tag}Date_Of_Birth", namespaces),
                "Gender_Reference": {
                    "Gender_Description": self.safe_find_text(biographic_data_elem, f"{namespace_tag}Gender_Reference/{namespace_tag}Gender_Description", namespaces)
                },
                "Uses_Tobacco": self.safe_find_text(biographic_data_elem, f"{namespace_tag}Uses_Tobacco", namespaces),
            } if biographic_data_elem is not None else None

            contact_data = {
                "Internet_Email_Address_Data": [
                    {
                        "Email_Address": self.safe_find_text(email_data_elem, f"{namespace_tag}Email_Address", namespaces),
                        "Usage_Data": {
                            "-Public": self.safe_get_attrib(email_data_elem.find(f"{namespace_tag}Usage_Data", namespaces), f"{namespace_tag}Public"),
                            "Type_Reference": {
                                "#content": self.safe_find_text(email_data_elem, f"{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces),
                                "-Primary": self.safe_get_attrib(email_data_elem.find(f"{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces), f"{namespace_tag}Primary")
                            }
                        }
                    }
                    for email_data_elem in contact_data_elem.findall(f"{namespace_tag}Internet_Email_Address_Data", namespaces)
                ],
                "Phone_Number_Data": {
                    "Country_ISO_Code": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}Country_ISO_Code", namespaces),
                    "International_Phone_Code": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}International_Phone_Code", namespaces),
                    "Area_Code": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}Area_Code", namespaces),
                    "Phone_Number": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}Phone_Number", namespaces),
                    "Phone_Device_Type_Reference": {
                        "Phone_Device_Type_Description": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}Phone_Device_Type_Reference/{namespace_tag}Phone_Device_Type_Description", namespaces)
                    },
                    "Usage_Data": {
                        "Type_Reference": {
                            "#content": self.safe_find_text(contact_data_elem, f"{namespace_tag}Phone_Number_Data/{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces),
                            "-Primary": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Phone_Number_Data/{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces), f"{namespace_tag}Primary"),
                        },
                        "-Public": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Phone_Number_Data/{namespace_tag}Usage_Data", namespaces), f"{namespace_tag}Public"),
                    }
                },
                "Address_Data": {
                    "Address_Line": [
                        {
                            "#content": address_line_elem.text,
                            "-Descriptor": self.safe_get_attrib(address_line_elem, f"{namespace_tag}Descriptor"),
                            "-Type": self.safe_get_attrib(address_line_elem, f"{namespace_tag}Type")
                        }
                        for address_line_elem in contact_data_elem.findall(f"{namespace_tag}Address_Data/{namespace_tag}Address_Line", namespaces)
                    ],
                    "Country_Reference": {
                        "Country_ISO_Code": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Country_Reference/{namespace_tag}Country_ISO_Code", namespaces)
                    },
                    "Municipality": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Municipality", namespaces),
                    "Postal_Code": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Postal_Code", namespaces),
                    "Region": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Region", namespaces),
                    "Subregion": {
                        "-Descriptor": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data/{namespace_tag}Subregion", namespaces), f"{namespace_tag}Descriptor"),
                        "-Type": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data/{namespace_tag}Subregion", namespaces), f"{namespace_tag}Type"),
                        "#content": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Subregion", namespaces)
                    },
                    "-Effective_Date": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data", namespaces), f"{namespace_tag}Effective_Date"),
                    "-Last_Modified": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data", namespaces), f"{namespace_tag}Last_Modified"),
                    "Usage_Data": {
                        "Type_Reference": {
                            "#content": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces),
                            "-Primary": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data/{namespace_tag}Usage_Data/{namespace_tag}Type_Reference", namespaces), f"{namespace_tag}Primary"),
                        },
                        "-Public": self.safe_get_attrib(contact_data_elem.find(f"{namespace_tag}Address_Data/{namespace_tag}Usage_Data", namespaces), f"{namespace_tag}Public"),
                        "Use_For_Reference": self.safe_find_text(contact_data_elem, f"{namespace_tag}Address_Data/{namespace_tag}Usage_Data/{namespace_tag}Use_For_Reference", namespaces)
                    }
                },
            } if contact_data_elem is not None else None

            demographic_data = {
                "Hispanic_or_Latino": self.safe_find_text(demographic_data_elem, f"{namespace_tag}Hispanic_or_Latino", namespaces),
                "Ethnicity_Reference": {
                    "Ethnicity_Name": self.safe_find_text(demographic_data_elem, f"{namespace_tag}Ethnicity_Reference/{namespace_tag}Ethnicity_Name", namespaces)
                },
            } if demographic_data_elem is not None else None

            name_data = {
                "-Effective_Date": self.safe_get_attrib(name_data_elem, f"{namespace_tag}Effective_Date"),
                "-Is_Legal": self.safe_get_attrib(name_data_elem, f"{namespace_tag}Is_Legal"),
                "-Is_Preferred": self.safe_get_attrib(name_data_elem, f"{namespace_tag}Is_Preferred"),
                "-Last_Modified": self.safe_get_attrib(name_data_elem, f"{namespace_tag}Last_Modified"),
                "Country_Reference": {
                    "Country_ISO_Code": self.safe_find_text(name_data_elem, f"{namespace_tag}Country_Reference/{namespace_tag}Country_ISO_Code", namespaces)
                },
                "First_Name": self.safe_find_text(name_data_elem, f"{namespace_tag}First_Name", namespaces),
                "Last_Name": {
                    "#content": self.safe_find_text(name_data_elem, f"{namespace_tag}Last_Name", namespaces),
                    "-Type": self.safe_get_attrib(name_data_elem.find(f"{namespace_tag}Last_Name", namespaces), f"{namespace_tag}Type"),
                },
                "Middle_Name": self.safe_find_text(name_data_elem, f"{namespace_tag}Middle_Name", namespaces),
            } if name_data_elem is not None else None

            worker_personal_data = {
                "Biographic_Data": biographic_data,
                "Contact_Data": contact_data,
                "Demographic_Data": demographic_data,
                "Name_Data": name_data,
            }

            worker_profile_data["Worker_Personal_Data"] = worker_personal_data
        

        worker_position_data_elem = worker_profile_data_elem.find(f"{namespace_tag}Worker_Position_Data", namespaces)

        if worker_position_data_elem is not None:
            worker_position_data = {
                "-Effective_Date": self.safe_get_attrib(worker_position_data_elem, f"{namespace_tag}Effective_Date"),
                "Position_ID": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Position_ID", namespaces),
                "Position_Title": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Position_Title", namespaces),
                "Job_Exempt": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Job_Exempt", namespaces),
                "Scheduled_Weekly_Hours": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Scheduled_Weekly_Hours", namespaces),
                "Default_Weekly_Hours": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Default_Weekly_Hours", namespaces),
                "Full_Time_Equivalent_Percentage": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Full_Time_Equivalent_Percentage", namespaces),
                "Specify_Paid_FTE": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Specify_Paid_FTE", namespaces),
                "Paid_FTE": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Paid_FTE", namespaces),
                "Specify_Working_FTE": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Specify_Working_FTE", namespaces),
                "Working_FTE": self.safe_find_text(worker_position_data_elem, f"{namespace_tag}Working_FTE", namespaces),
            }

            position_reference_elem = worker_position_data_elem.find(f"{namespace_tag}Position_Reference", namespaces)
            position_reference = {
                "Integration_ID_Reference": {
                    "-Descriptor": self.safe_get_attrib(position_reference_elem.find(f"{namespace_tag}Integration_ID_Reference", namespaces), f"{namespace_tag}Descriptor"),
                    "ID": [
                        {
                            "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                            "#content": id_elem.text
                        }
                        for id_elem in position_reference_elem.findall(f"{namespace_tag}Integration_ID_Reference/{namespace_tag}ID", namespaces)
                    ]
                }
            } if position_reference_elem is not None else None

            employee_type_reference_elem = worker_position_data_elem.find(f"{namespace_tag}Employee_Type_Reference", namespaces)
            employee_type_reference = {
                "Employee_Type_Description": self.safe_find_text(employee_type_reference_elem, f"{namespace_tag}Employee_Type_Description", namespaces)
            } if employee_type_reference_elem is not None else None

            position_time_type_reference_elem = worker_position_data_elem.find(f"{namespace_tag}Position_Time_Type_Reference", namespaces)
            position_time_type_reference = {
                "Time_Type_Description": self.safe_find_text(position_time_type_reference_elem, f"{namespace_tag}Time_Type_Description", namespaces)
            } if position_time_type_reference_elem is not None else None

            job_profile_summary_data_elem = worker_position_data_elem.find(f"{namespace_tag}Job_Profile_Summary_Data", namespaces)
            job_profile_summary_data = {
                "Job_Profile_Reference": {
                    "ID": [
                        {
                            "-type": self.safe_get_attrib(id_elem, f"{namespace_tag}type"),
                            "#content": id_elem.text
                        }
                        for id_elem in job_profile_summary_data_elem.findall(f"{namespace_tag}Job_Profile_Reference/{namespace_tag}ID", namespaces)
                    ]
                },
                "Job_Exempt": self.safe_find_text(job_profile_summary_data_elem, f"{namespace_tag}Job_Exempt", namespaces),
                "Management_Level_Reference": {
                    "ID": [
                        {
                            "-type": self.safe_get_attrib(id_elem, f"{namespace_tag}type"),
                            "#content": id_elem.text
                        }
                        for id_elem in job_profile_summary_data_elem.findall(f"{namespace_tag}Management_Level_Reference/{namespace_tag}ID", namespaces)
                    ]
                },
                "Job_Family_Reference": {
                    "ID": [
                        {
                            "-type": self.safe_get_attrib(id_elem, f"{namespace_tag}type"),
                            "#content": id_elem.text
                        }
                        for id_elem in job_profile_summary_data_elem.findall(f"{namespace_tag}Job_Family_Reference/{namespace_tag}ID", namespaces)
                    ]
                },
                "Job_Category_Reference": {
                    "ID": [
                        {
                            "-type": self.safe_get_attrib(id_elem, f"{namespace_tag}type"),
                            "#content": id_elem.text
                        }
                        for id_elem in job_profile_summary_data_elem.findall(f"{namespace_tag}Job_Category_Reference/{namespace_tag}ID", namespaces)
                    ]
                },
                "Job_Profile_Name": self.safe_find_text(job_profile_summary_data_elem, f"{namespace_tag}Job_Profile_Name", namespaces),
                "Work_Shift_Required": self.safe_find_text(job_profile_summary_data_elem, f"{namespace_tag}Work_Shift_Required", namespaces),
                "Critical_Job": self.safe_find_text(job_profile_summary_data_elem, f"{namespace_tag}Critical_Job", namespaces)
            } if job_profile_summary_data_elem is not None else None

            organization_content_data_elems = worker_position_data_elem.findall(f"{namespace_tag}Organization_Content_Data", namespaces) if worker_position_data_elem is not None else []
            organization_content_data = [
                {
                    "Integration_ID_Data": {
                        "ID": [
                            {
                                "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                                "#content": id_elem.text
                            }
                            for id_elem in org_content_elem.findall(f"{namespace_tag}Integration_ID_Data/{namespace_tag}ID", namespaces)
                        ]
                    },
                    "Organization_ID": self.safe_find_text(org_content_elem, f"{namespace_tag}Organization_ID", namespaces),
                    "Organization_Name": self.safe_find_text(org_content_elem, f"{namespace_tag}Organization_Name", namespaces),
                    "Organization_Type_Reference": {
                        "Organization_Type_Name": self.safe_find_text(org_content_elem, f"{namespace_tag}Organization_Type_Reference/{namespace_tag}Organization_Type_Name", namespaces)
                    },
                    "Organization_Subtype_Reference": {
                        "Organization_Subtype_Name": self.safe_find_text(org_content_elem, f"{namespace_tag}Organization_Subtype_Reference/{namespace_tag}Organization_Subtype_Name", namespaces)
                    }
                }
                for org_content_elem in organization_content_data_elems
            ]

            business_site_content_data_elem = worker_position_data_elem.find(f"{namespace_tag}Business_Site_Content_Data", namespaces)
            business_site_content_data = {
                "Integration_ID_Data": {
                    "ID": [
                        {
                            "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                            "#content": id_elem.text
                        }
                        for id_elem in business_site_content_data_elem.findall(f"{namespace_tag}Integration_ID_Data/{namespace_tag}ID", namespaces)
                    ]
                },
                "Location_Name": self.safe_find_text(business_site_content_data_elem, f"{namespace_tag}Location_Name", namespaces),
                "Location_Type_Reference": {
                    "Location_Type_Description": self.safe_find_text(business_site_content_data_elem, f"{namespace_tag}Location_Type_Reference/{namespace_tag}Location_Type_Description", namespaces)
                },
                "Time_Profile_Reference": {
                    "Time_Profile_Description": self.safe_find_text(business_site_content_data_elem, f"{namespace_tag}Time_Profile_Reference/{namespace_tag}Time_Profile_Description", namespaces)
                }
            } if business_site_content_data_elem is not None else None

            payroll_processing_data_elem = worker_position_data_elem.find(f"{namespace_tag}Payroll_Processing_Data", namespaces)
            payroll_processing_data = {
                "Frequency_Reference": {
                    "Frequency_Name": self.safe_find_text(payroll_processing_data_elem, f"{namespace_tag}Frequency_Reference/{namespace_tag}Frequency_Name", namespaces)
                }
            } if payroll_processing_data_elem is not None else None

            supervisor_reference_elem = worker_position_data_elem.find(f"{namespace_tag}Supervisor_Reference", namespaces)
            supervisor_reference = {
                "Employee_Reference": {
                    "Integration_ID_Reference": {
                        "-Descriptor": self.safe_get_attrib(supervisor_reference_elem.find(f"{namespace_tag}Employee_Reference/{namespace_tag}Integration_ID_Reference", namespaces), f"{namespace_tag}Descriptor"),
                        "ID": [
                            {
                                "-System_ID": self.safe_get_attrib(id_elem, f"{namespace_tag}System_ID"),
                                "#content": id_elem.text
                            }
                            for id_elem in supervisor_reference_elem.findall(f"{namespace_tag}Employee_Reference/{namespace_tag}Integration_ID_Reference/{namespace_tag}ID", namespaces)
                        ]
                    }
                }
            } if supervisor_reference_elem is not None else None

            worker_position_data["Position_Reference"] = position_reference
            worker_position_data["Employee_Type_Reference"] = employee_type_reference
            worker_position_data["Position_Time_Type_Reference"] = position_time_type_reference
            worker_position_data["Job_Profile_Summary_Data"] = job_profile_summary_data
            worker_position_data["Organization_Content_Data"] = organization_content_data
            worker_position_data["Business_Site_Content_Data"] = business_site_content_data
            worker_position_data["Payroll_Processing_Data"] = payroll_processing_data
            worker_position_data["Supervisor_Reference"] = supervisor_reference

            worker_profile_data["Worker_Position_Data"] = worker_position_data
        
        profile_data["Worker_Profile_Data"] = worker_profile_data
        return [profile_data]



    def parse_organization_hierarchies_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        organization_hierarchies: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

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
                "Availibility_Date": self.safe_find_text(
                    org_data_elem, "{urn:com.workday/bsvc}Availibility_Date", namespaces
                ),
                "Last_Updated_DateTime": self.safe_find_text(
                    org_data_elem, "{urn:com.workday/bsvc}Last_Updated_DateTime", namespaces
                ),
                "Inactive": self.safe_find_text(org_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces),
                "Include_Manager_in_Name": self.safe_find_text(
                    org_data_elem, "{urn:com.workday/bsvc}Include_Manager_in_Name", namespaces
                ),
                "Include_Organization_Code_in_Name": self.safe_find_text(
                    org_data_elem, "{urn:com.workday/bsvc}Include_Organization_Code_in_Name", namespaces
                ),
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
        self, response_data: ET.Element, namespaces: Dict[str, str]
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
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in ethnicity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in ethnicity_data_elem.find(
                            "{urn:com.workday/bsvc}Location_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if ethnicity_data_elem.find("{urn:com.workday/bsvc}Location_Reference", namespaces) is not None
                    else []
                )
            }

            ethnicity_mapping_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in ethnicity_data_elem.find(
                            "{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if ethnicity_data_elem.find("{urn:com.workday/bsvc}Ethnicity_Mapping_Reference", namespaces)
                    is not None
                    else []
                )
            }

            ethnicity_data = {
                "ID": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                "Name": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}Name", namespaces),
                "Description": self.safe_find_text(
                    ethnicity_data_elem, "{urn:com.workday/bsvc}Description", namespaces
                ),
                "Location_Reference": location_reference,
                "Ethnicity_Mapping_Reference": ethnicity_mapping_reference,
                "Inactive": self.safe_find_text(ethnicity_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces),
            }

            ethnicities.append({"Ethnicity_Reference": ethnicity_reference, "Ethnicity_Data": ethnicity_data})

        return ethnicities

    def parse_gender_identities_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        gender_identities: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return gender_identities

        for gender_identity in response_data.findall("{urn:com.workday/bsvc}Gender_Identity", namespaces):
            gender_identity_reference_elem = gender_identity.find(
                "{urn:com.workday/bsvc}Gender_Identity_Reference", namespaces
            )
            gender_identity_data_elem = gender_identity.find("{urn:com.workday/bsvc}Gender_Identity_Data", namespaces)

            gender_identity_reference = {
                "ID": [
                    {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in gender_identity_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            gender_identity_data = {
                "ID": self.safe_find_text(gender_identity_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                "Gender_Identity_Name": self.safe_find_text(
                    gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Name", namespaces
                ),
                "Gender_Identity_Code": self.safe_find_text(
                    gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Code", namespaces
                ),
                "Gender_Identity_Inactive": self.safe_find_text(
                    gender_identity_data_elem, "{urn:com.workday/bsvc}Gender_Identity_Inactive", namespaces
                ),
            }

            gender_identities.append(
                {"Gender_Identity_Reference": gender_identity_reference, "Gender_Identity_Data": gender_identity_data}
            )

        return gender_identities

    def parse_locations_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
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
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                    for id_elem in location_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                ]
            }

            location_usage_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Location_Usage_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Location_Usage_Reference", namespaces) is not None
                    else []
                )
            }

            location_type_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Location_Type_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Location_Type_Reference", namespaces) is not None
                    else []
                )
            }

            location_hierarchy_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Location_Hierarchy_Reference", namespaces)
                    is not None
                    else []
                )
            }

            time_profile_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Time_Profile_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Time_Profile_Reference", namespaces) is not None
                    else []
                )
            }

            integration_id_data = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-System_ID": id_elem.attrib.get("{urn:com.workday/bsvc}System_ID", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Integration_ID_Data", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Integration_ID_Data", namespaces) is not None
                    else []
                )
            }

            locale_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Locale_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Locale_Reference", namespaces) is not None
                    else []
                )
            }

            time_zone_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Time_Zone_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Time_Zone_Reference", namespaces) is not None
                    else []
                )
            }

            default_currency_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in location_data_elem.find(
                            "{urn:com.workday/bsvc}Default_Currency_Reference", namespaces
                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if location_data_elem.find("{urn:com.workday/bsvc}Default_Currency_Reference", namespaces)
                    is not None
                    else []
                )
            }

            contact_data_elem = location_data_elem.find("{urn:com.workday/bsvc}Contact_Data", namespaces)
            address_data_elem = (
                contact_data_elem.find("{urn:com.workday/bsvc}Address_Data", namespaces)
                if contact_data_elem is not None
                else None
            )
            address_data = (
                {
                    "-Address_Format_Type": address_data_elem.attrib.get("{urn:com.workday/bsvc}Address_Format_Type"),
                    "-Defaulted_Business_Site_Address": address_data_elem.attrib.get(
                        "{urn:com.workday/bsvc}Defaulted_Business_Site_Address"
                    ),
                    "-Effective_Date": address_data_elem.attrib.get("{urn:com.workday/bsvc}Effective_Date"),
                    "-Formatted_Address": address_data_elem.attrib.get("{urn:com.workday/bsvc}Formatted_Address"),
                    "Address_ID": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Address_ID", namespaces
                    ),
                    "Address_Line_Data": {
                        "#content": self.safe_find_text(
                            address_data_elem, "{urn:com.workday/bsvc}Address_Line_Data", namespaces
                        ),
                        "-Descriptor": address_data_elem.find(
                            "{urn:com.workday/bsvc}Address_Line_Data", namespaces
                        ).attrib.get("{urn:com.workday/bsvc}Descriptor"),
                        "-Type": address_data_elem.find(
                            "{urn:com.workday/bsvc}Address_Line_Data", namespaces
                        ).attrib.get("{urn:com.workday/bsvc}Type"),
                    },
                    "Address_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in address_data_elem.find(
                                    "{urn:com.workday/bsvc}Address_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if address_data_elem.find("{urn:com.workday/bsvc}Address_Reference", namespaces) is not None
                            else []
                        )
                    },
                    "Country_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in address_data_elem.find(
                                    "{urn:com.workday/bsvc}Country_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if address_data_elem.find("{urn:com.workday/bsvc}Country_Reference", namespaces) is not None
                            else []
                        )
                    },
                    "Country_Region_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in address_data_elem.find(
                                    "{urn:com.workday/bsvc}Country_Region_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if address_data_elem.find("{urn:com.workday/bsvc}Country_Region_Reference", namespaces)
                            is not None
                            else []
                        )
                    },
                    "Country_Region_Descriptor": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Country_Region_Descriptor", namespaces
                    ),
                    "Last_Modified": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Last_Modified", namespaces
                    ),
                    "Municipality": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Municipality", namespaces
                    ),
                    "Number_of_Days": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Number_of_Days", namespaces
                    ),
                    "Postal_Code": self.safe_find_text(
                        address_data_elem, "{urn:com.workday/bsvc}Postal_Code", namespaces
                    ),
                    "Usage_Data": {
                        "-Public": address_data_elem.find("{urn:com.workday/bsvc}Usage_Data", namespaces).attrib.get(
                            "{urn:com.workday/bsvc}Public"
                        ),
                        "Type_Data": {
                            "-Primary": address_data_elem.find(
                                "{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data", namespaces
                            ).attrib.get("{urn:com.workday/bsvc}Primary"),
                            "Type_Reference": {
                                "ID": (
                                    [
                                        {
                                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                        }
                                        for id_elem in address_data_elem.find(
                                            "{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference",
                                            namespaces,
                                        ).findall("{urn:com.workday/bsvc}ID", namespaces)
                                    ]
                                    if address_data_elem.find(
                                        "{urn:com.workday/bsvc}Usage_Data/{urn:com.workday/bsvc}Type_Data/{urn:com.workday/bsvc}Type_Reference",
                                        namespaces,
                                    )
                                    is not None
                                    else []
                                )
                            },
                        },
                    },
                }
                if address_data_elem is not None
                else None
            )

            contact_data = {"Address_Data": address_data}

            location_data = {
                "Location_ID": self.safe_find_text(location_data_elem, "{urn:com.workday/bsvc}Location_ID", namespaces),
                "Location_Name": self.safe_find_text(
                    location_data_elem, "{urn:com.workday/bsvc}Location_Name", namespaces
                ),
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

            locations.append({"Location_Reference": location_reference, "Location_Data": location_data})

        return locations

    def parse_job_profiles_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        job_profiles: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return job_profiles

        for job_profile in response_data.findall("{urn:com.workday/bsvc}Job_Profile", namespaces):
            job_profile_reference_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Reference", namespaces)
            job_profile_data_elem = job_profile.find("{urn:com.workday/bsvc}Job_Profile_Data", namespaces)

            job_profile_reference = {
                "ID": (
                    [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in job_profile_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                    if job_profile_reference_elem is not None
                    else []
                )
            }

            job_profile_basic_data_elem = (
                job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Basic_Data", namespaces)
                if job_profile_data_elem is not None
                else None
            )
            job_profile_pay_rate_data_elem = (
                job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Pay_Rate_Data", namespaces)
                if job_profile_data_elem is not None
                else None
            )
            job_profile_exempt_data_elem = (
                job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Exempt_Data", namespaces)
                if job_profile_data_elem is not None
                else None
            )
            job_profile_compensation_data_elem = (
                job_profile_data_elem.find("{urn:com.workday/bsvc}Job_Profile_Compensation_Data", namespaces)
                if job_profile_data_elem is not None
                else None
            )
            job_classification_data_elems = (
                job_profile_data_elem.findall("{urn:com.workday/bsvc}Job_Classification_Data", namespaces)
                if job_profile_data_elem is not None
                else []
            )
            workers_compensation_code_replacement_data_elem = (
                job_profile_data_elem.find(
                    "{urn:com.workday/bsvc}Workers_Compensation_Code_Replacement_Data", namespaces
                )
                if job_profile_data_elem is not None
                else None
            )

            job_profile_basic_data = {}

            if job_profile_basic_data_elem is not None:
                job_profile_basic_data["Job_Title"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Job_Title", namespaces
                )
                job_profile_basic_data["Inactive"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Inactive", namespaces
                )
                job_profile_basic_data["Include_Job_Code_in_Name"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Include_Job_Code_in_Name", namespaces
                )
                job_profile_basic_data["Work_Shift_Required"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Work_Shift_Required", namespaces
                )
                job_profile_basic_data["Public_Job"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Public_Job", namespaces
                )
                job_profile_basic_data["Critical_Job"] = self.safe_find_text(
                    job_profile_basic_data_elem, "{urn:com.workday/bsvc}Critical_Job", namespaces
                )

                job_family_data_elem = job_profile_basic_data_elem.find(
                    "{urn:com.workday/bsvc}Job_Family_Data", namespaces
                )
                job_family_data = (
                    {
                        "Job_Family_Reference": {
                            "ID": (
                                [
                                    {
                                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                    }
                                    for id_elem in job_family_data_elem.find(
                                        "{urn:com.workday/bsvc}Job_Family_Reference", namespaces
                                    ).findall("{urn:com.workday/bsvc}ID", namespaces)
                                ]
                                if job_family_data_elem.find("{urn:com.workday/bsvc}Job_Family_Reference", namespaces)
                                is not None
                                else []
                            )
                        }
                    }
                    if job_family_data_elem is not None
                    else None
                )

                job_level_reference = {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in job_profile_basic_data_elem.find(
                                "{urn:com.workday/bsvc}Job_Level_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Level_Reference", namespaces)
                        is not None
                        else []
                    )
                }

                management_level_reference = {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in job_profile_basic_data_elem.find(
                                "{urn:com.workday/bsvc}Management_Level_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if job_profile_basic_data_elem.find(
                            "{urn:com.workday/bsvc}Management_Level_Reference", namespaces
                        )
                        is not None
                        else []
                    )
                }

                referral_payment_plan_reference = {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in job_profile_basic_data_elem.find(
                                "{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces
                            ).findall("{urn:com.workday/bsvc}ID", namespaces)
                        ]
                        if job_profile_basic_data_elem.find(
                            "{urn:com.workday/bsvc}Referral_Payment_Plan_Reference", namespaces
                        )
                        is not None
                        else []
                    )
                }

                job_profile_basic_data["Job_Family_Data"] = job_family_data
                job_profile_basic_data["Job_Level_Reference"] = job_level_reference
                job_profile_basic_data["Management_Level_Reference"] = management_level_reference
                job_profile_basic_data["Referral_Payment_Plan_Reference"] = referral_payment_plan_reference

                job_description = job_profile_basic_data_elem.find("{urn:com.workday/bsvc}Job_Description", namespaces)
                if job_description is not None:
                    job_profile_basic_data["Job_Description"] = job_description.text

            job_profile_pay_rate_data = (
                {
                    "Country_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in job_profile_pay_rate_data_elem.find(
                                    "{urn:com.workday/bsvc}Country_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if job_profile_pay_rate_data_elem is not None
                            and job_profile_pay_rate_data_elem.find(
                                "{urn:com.workday/bsvc}Country_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    },
                    "Pay_Rate_Type_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in job_profile_pay_rate_data_elem.find(
                                    "{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if job_profile_pay_rate_data_elem is not None
                            and job_profile_pay_rate_data_elem.find(
                                "{urn:com.workday/bsvc}Pay_Rate_Type_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    },
                }
                if job_profile_pay_rate_data_elem is not None
                else None
            )

            workers_compensation_code_replacement_data = (
                {
                    "Workers_Compensation_Code_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in workers_compensation_code_replacement_data_elem.find(
                                    "{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if workers_compensation_code_replacement_data_elem.find(
                                "{urn:com.workday/bsvc}Workers_Compensation_Code_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    }
                }
                if workers_compensation_code_replacement_data_elem is not None
                else None
            )

            job_profile_exempt_data = (
                {
                    "Location_Context_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in job_profile_exempt_data_elem.find(
                                    "{urn:com.workday/bsvc}Location_Context_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if job_profile_exempt_data_elem is not None
                            and job_profile_exempt_data_elem.find(
                                "{urn:com.workday/bsvc}Location_Context_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    },
                    "Job_Exempt": self.safe_find_text(
                        job_profile_exempt_data_elem, "{urn:com.workday/bsvc}Job_Exempt", namespaces
                    ),
                }
                if job_profile_exempt_data_elem is not None
                else None
            )

            job_profile_compensation_data = (
                {
                    "Compensation_Grade_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in job_profile_compensation_data_elem.find(
                                    "{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if job_profile_compensation_data_elem is not None
                            and job_profile_compensation_data_elem.find(
                                "{urn:com.workday/bsvc}Compensation_Grade_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    }
                }
                if job_profile_compensation_data_elem is not None
                else None
            )

            job_classifications_data = [
                {
                    "Job_Classifications_Reference": {
                        "ID": (
                            [
                                {
                                    "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                    "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                                }
                                for id_elem in job_classification_data_elem.find(
                                    "{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces
                                ).findall("{urn:com.workday/bsvc}ID", namespaces)
                            ]
                            if job_classification_data_elem.find(
                                "{urn:com.workday/bsvc}Job_Classifications_Reference", namespaces
                            )
                            is not None
                            else []
                        )
                    }
                }
                for job_classification_data_elem in job_classification_data_elems
            ]

            job_profile_data = {
                "Job_Code": self.safe_find_text(job_profile_data_elem, "{urn:com.workday/bsvc}Job_Code", namespaces),
                "Effective_Date": self.safe_find_text(
                    job_profile_data_elem, "{urn:com.workday/bsvc}Effective_Date", namespaces
                ),
                "Job_Profile_Basic_Data": job_profile_basic_data,
                "Job_Profile_Pay_Rate_Data": job_profile_pay_rate_data,
                "Workers_Compensation_Code_Replacement_Data": workers_compensation_code_replacement_data,
                "Job_Profile_Exempt_Data": job_profile_exempt_data,
                "Job_Profile_Compensation_Data": job_profile_compensation_data,
                "Job_Classification_Data": job_classifications_data,
            }

            job_profiles.append({"Job_Profile_Reference": job_profile_reference, "Job_Profile_Data": job_profile_data})

        return job_profiles

    def parse_positions_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        positions: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return positions

        for position in response_data.findall("{urn:com.workday/bsvc}Position", namespaces):
            position_reference_elem = position.find("{urn:com.workday/bsvc}Position_Reference", namespaces)
            position_data_elem = position.find("{urn:com.workday/bsvc}Position_Data", namespaces)

            position_reference = (
                {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in position_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                }
                if position_reference_elem is not None
                else None
            )

            position_definition_data_elem = (
                position_data_elem.find("{urn:com.workday/bsvc}Position_Definition_Data", namespaces)
                if position_data_elem is not None
                else None
            )

            position_definition_data = {
                "Position_ID": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Position_ID", namespaces
                ),
                "Job_Posting_Title": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Job_Posting_Title", namespaces
                ),
                "Academic_Tenure_Eligible": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Academic_Tenure_Eligible", namespaces
                ),
                "Available_For_Hire": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Available_For_Hire", namespaces
                ),
                "Available_for_Recruiting": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Available_for_Recruiting", namespaces
                ),
                "Hiring_Freeze": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Hiring_Freeze", namespaces
                ),
                "Work_Shift_Required": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Work_Shift_Required", namespaces
                ),
                "Available_for_Overlap": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Available_for_Overlap", namespaces
                ),
                "Critical_Job": self.safe_find_text(
                    position_definition_data_elem, "{urn:com.workday/bsvc}Critical_Job", namespaces
                ),
            }

            position_status_reference = [
                {
                    "ID": {
                        "#content": id_elem.text if id_elem is not None else "Unknown ID",
                        "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                    }
                }
                for id_elem in position_definition_data_elem.findall(
                    "{urn:com.workday/bsvc}Position_Status_Reference/{urn:com.workday/bsvc}ID", namespaces
                )
            ]
            position_definition_data["Position_Status_Reference"] = position_status_reference

            position_data = {
                "Supervisory_Organization_Reference": {
                    "ID": (
                        [
                            {
                                "#content": id_elem.text if id_elem is not None else "Unknown ID",
                                "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                            }
                            for id_elem in position_data_elem.findall(
                                "{urn:com.workday/bsvc}Supervisory_Organization_Reference/{urn:com.workday/bsvc}ID",
                                namespaces,
                            )
                        ]
                        if position_data_elem is not None
                        else []
                    )
                },
                "Effective_Date": self.safe_find_text(
                    position_data_elem, "{urn:com.workday/bsvc}Effective_Date", namespaces
                ),
                "Position_Definition_Data": position_definition_data,
                "Closed": self.safe_find_text(position_data_elem, "{urn:com.workday/bsvc}Closed", namespaces),
            }

            positions.append({"Position_Reference": position_reference, "Position_Data": position_data})

        return positions

    def parse_sexual_orientations_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        sexual_orientations: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return sexual_orientations

        for orientation in response_data.findall("{urn:com.workday/bsvc}Sexual_Orientation", namespaces):
            orientation_reference_elem = orientation.find(
                "{urn:com.workday/bsvc}Sexual_Orientation_Reference", namespaces
            )
            orientation_data_elem = orientation.find("{urn:com.workday/bsvc}Sexual_Orientation_Data", namespaces)

            orientation_reference = (
                {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in orientation_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                }
                if orientation_reference_elem is not None
                else None
            )

            orientation_data = {}
            if orientation_data_elem is not None:
                orientation_data["ID"] = self.safe_find_text(
                    orientation_data_elem, "{urn:com.workday/bsvc}ID", namespaces
                )
                orientation_data["Sexual_Orientation_Name"] = self.safe_find_text(
                    orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Name", namespaces
                )
                orientation_data["Sexual_Orientation_Code"] = self.safe_find_text(
                    orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Code", namespaces
                )
                orientation_data["Sexual_Orientation_Description"] = self.safe_find_text(
                    orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Description", namespaces
                )
                orientation_data["Sexual_Orientation_Inactive"] = self.safe_find_text(
                    orientation_data_elem, "{urn:com.workday/bsvc}Sexual_Orientation_Inactive", namespaces
                )

            sexual_orientations.append(
                {"Sexual_Orientation_Reference": orientation_reference, "Sexual_Orientation_Data": orientation_data}
            )

        return sexual_orientations

    def parse_references_response(
        self, response_data: ET.Element, namespaces: Dict[str, str]
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        references: List[Dict[str, Optional[Union[str, List[Dict[str, str]]]]]] = []

        if response_data is None:
            return references

        for reference in response_data.findall("{urn:com.workday/bsvc}Reference_ID", namespaces):
            reference_descriptor = reference.attrib.get("{urn:com.workday/bsvc}Descriptor")
            reference_id_reference_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Reference", namespaces)
            reference_id_data_elem = reference.find("{urn:com.workday/bsvc}Reference_ID_Data", namespaces)

            reference_id_reference = (
                {
                    "ID": [
                        {
                            "#content": id_elem.text if id_elem is not None else "Unknown ID",
                            "-type": id_elem.attrib.get("{urn:com.workday/bsvc}type", "Unknown Type"),
                        }
                        for id_elem in reference_id_reference_elem.findall("{urn:com.workday/bsvc}ID", namespaces)
                    ]
                }
                if reference_id_reference_elem is not None
                else None
            )

            reference_id_data = (
                {
                    "ID": self.safe_find_text(reference_id_data_elem, "{urn:com.workday/bsvc}ID", namespaces),
                    "Reference_ID_Type": self.safe_find_text(
                        reference_id_data_elem, "{urn:com.workday/bsvc}Reference_ID_Type", namespaces
                    ),
                    "Referenced_Object_Descriptor": self.safe_find_text(
                        reference_id_data_elem, "{urn:com.workday/bsvc}Referenced_Object_Descriptor", namespaces
                    ),
                }
                if reference_id_data_elem is not None
                else None
            )

            references.append(
                {
                    "-Descriptor": reference_descriptor,
                    "Reference_ID_Reference": reference_id_reference,
                    "Reference_ID_Data": reference_id_data,
                }
            )

        return references

    def parse_base_snapshot_report_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        response_csv = response.content.decode("utf-8")
        reader = csv.DictReader(response_csv.splitlines())

        return [row for row in reader]

    def parse_base_historical_report_compensation_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:

        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = self.get_namespaces(root)
        namespace_tag = namespaces["wd"]

        main_compensation_tag = ""
        sub_compensation_tag = ""

        # Tags can vary depending on the way the Workday integration was setup
        if (
            "Compensation_History_-_Previous_System_group" in xml_data
            and "Compensation_History_Record_from_Previous_System" in xml_data
        ):
            main_compensation_tag = "Compensation_History_-_Previous_System_group"
            sub_compensation_tag = "Compensation_History_Record_from_Previous_System"
        elif (
            "Job_History_from_Previous_System_group" in xml_data
            and "Job_Position_History_Record_from_Previous_System" in xml_data
        ):
            main_compensation_tag = "Job_History_from_Previous_System_group"
            sub_compensation_tag = "Job_Position_History_Record_from_Previous_System"

        compensation_records: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        for report_entry in root.findall(f".//{{{namespace_tag}}}Report_Entry", namespaces):
            employee_id = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Employee_ID", namespaces)
            worker_elem = report_entry.find(f"{{{namespace_tag}}}Worker", namespaces)
            worker_descriptor = (
                worker_elem.attrib.get(f"{{{namespace_tag}}}Descriptor") if worker_elem is not None else None
            )
            worker_ids = (
                [
                    {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                    for id_elem in worker_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                ]
                if worker_elem is not None
                else []
            )

            compensation_history = []
            for history_elem in report_entry.findall(f"{{{namespace_tag}}}{main_compensation_tag}", namespaces):
                compensation_history_entry_elem = history_elem.find(
                    f"{{{namespace_tag}}}{sub_compensation_tag}", namespaces
                )
                currency_elem = history_elem.find(f"{{{namespace_tag}}}Currency", namespaces)
                frequency_elem = history_elem.find(f"{{{namespace_tag}}}Frequency", namespaces)

                compensation_history_item = {
                    "Worker_History_Name": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Worker_History_Name", namespaces
                    ),
                    "Effective_Date": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Effective_Date", namespaces
                    ),
                    "Reason": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Reason", namespaces),
                    "Amount": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount", namespaces),
                    "Amount_Change": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Amount_Change", namespaces),
                }

                if compensation_history_entry_elem is not None:
                    compensation_history_item[sub_compensation_tag] = {
                        "-Descriptor": compensation_history_entry_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in compensation_history_entry_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                if currency_elem is not None:
                    compensation_history_item["Currency"] = {
                        "-Descriptor": currency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in currency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                if frequency_elem is not None:
                    compensation_history_item["Frequency"] = {
                        "-Descriptor": frequency_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"-type": id_elem.attrib.get(f"{{{namespace_tag}}}type"), "#content": id_elem.text}
                            for id_elem in frequency_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                compensation_history.append(compensation_history_item)

            record = {"Employee_ID": employee_id, "Worker": {"-Descriptor": worker_descriptor, "ID": worker_ids}}

            if len(compensation_history) > 0:
                record[main_compensation_tag] = compensation_history

            compensation_records.append(record)

        return compensation_records

    def parse_base_historical_report_job_response(
        self, response: requests.Response
    ) -> List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]]:
        xml_data = response.text
        root = ET.fromstring(xml_data)

        namespaces = self.get_namespaces(root)
        namespace_tag = namespaces["wd"]

        # TODO: Hardcoded for now because only 1 client is using this. Need to make it dynamic in the future
        main_job_tag = "Job_History_from_Previous_System_group"
        sub_job_tag = "History_Record"

        job_records: List[Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]] = []

        def get_all_positions_group_data(
            all_positions_group_elem: ET.Element,
        ) -> Dict[str, Optional[Union[str | None, List[Dict[str, str]]]]]:
            position_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Position", namespaces)
            position_worker_type_elem = all_positions_group_elem.find(
                f"{{{namespace_tag}}}Position_Worker_Type", namespaces
            )
            time_type_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Time_Type", namespaces)
            position_manager_elem = all_positions_group_elem.find(f"{{{namespace_tag}}}Position_Manager", namespaces)

            all_positions_group_data = {
                "Business_Title": self.safe_find_text(
                    all_positions_group_elem, f"{{{namespace_tag}}}Business_Title", namespaces
                )
            }

            if position_elem is not None:
                all_positions_group_data["Position"] = {
                    "-Descriptor": position_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": {
                        "#content": self.safe_find_text(position_elem, f"{{{namespace_tag}}}ID", namespaces),
                        "-type": position_elem.find(f"{{{namespace_tag}}}ID").attrib.get(f"{{{namespace_tag}}}type"),
                    },
                }

            if position_worker_type_elem is not None:
                all_positions_group_data["Position_Worker_Type"] = {
                    "-Descriptor": position_worker_type_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in position_worker_type_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            if time_type_elem is not None:
                all_positions_group_data["Time_Type"] = {
                    "-Descriptor": time_type_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in time_type_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            if position_manager_elem is not None:
                all_positions_group_data["Position_Manager"] = {
                    "-Descriptor": position_manager_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in position_manager_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }

            return all_positions_group_data

        for report_entry in root.findall(f".//{{{namespace_tag}}}Report_Entry", namespaces):
            all_positions_group_elems = report_entry.findall(f"{{{namespace_tag}}}All_Positions_group", namespaces)

            if len(all_positions_group_elems) > 1:
                all_positions_group_data = []
                for all_positions_group_elem in all_positions_group_elems:
                    all_positions_group_data.append(get_all_positions_group_data(all_positions_group_elem))

            elif len(all_positions_group_elems) == 1:
                all_positions_group_data = get_all_positions_group_data(all_positions_group_elems[0])

            else:
                all_positions_group_data = None

            employee_id = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Employee_ID", namespaces)
            hire_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Hire_Date", namespaces)
            original_hire_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Original_Hire_Date", namespaces)
            termination_reason = self.safe_find_text(report_entry, f"{{{namespace_tag}}}Termination_Reason", namespaces)
            termination_date = self.safe_find_text(report_entry, f"{{{namespace_tag}}}termination_date", namespaces)
            termination_regret = self.safe_find_text(report_entry, f"{{{namespace_tag}}}termination_regret", namespaces)
            termination_category_elem = report_entry.find(f"{{{namespace_tag}}}Termination_Category", namespaces)
            termination_category = (
                {
                    "-Descriptor": termination_category_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in termination_category_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }
                if termination_category_elem is not None
                else None
            )

            worker_elem = report_entry.find(f"{{{namespace_tag}}}Worker", namespaces)
            worker = (
                {
                    "-Descriptor": worker_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                    "ID": [
                        {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                        for id_elem in worker_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                    ],
                }
                if worker_elem is not None
                else None
            )

            job_history = []
            for history_elem in report_entry.findall(f"{{{namespace_tag}}}{main_job_tag}", namespaces):
                job_history_entry_elem = history_elem.find(f"{{{namespace_tag}}}{sub_job_tag}", namespaces)

                job_history_item = {
                    "Compensation": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Compensation", namespaces),
                    "Department": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Department", namespaces),
                    "Effective_Date": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Effective_Date", namespaces
                    ),
                    "Function": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Function", namespaces),
                    "Hourly_Salaried": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Hourly_Salaried", namespaces
                    ),
                    "Job_Title": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Job_Title", namespaces),
                    "Location": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Location", namespaces),
                    "Manager": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Manager", namespaces),
                    "Reason": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Reason", namespaces),
                    "Salary_Grade": self.safe_find_text(history_elem, f"{{{namespace_tag}}}Salary_Grade", namespaces),
                    "Worker_History_Name": self.safe_find_text(
                        history_elem, f"{{{namespace_tag}}}Worker_History_Name", namespaces
                    ),
                }

                if job_history_entry_elem is not None:
                    job_history_item[sub_job_tag] = {
                        "-Descriptor": job_history_entry_elem.attrib.get(f"{{{namespace_tag}}}Descriptor"),
                        "ID": [
                            {"#content": id_elem.text, "-type": id_elem.attrib.get(f"{{{namespace_tag}}}type")}
                            for id_elem in job_history_entry_elem.findall(f"{{{namespace_tag}}}ID", namespaces)
                        ],
                    }

                job_history.append(job_history_item)

            record = {
                "Employee_ID": employee_id,
                "All_Positions_group": all_positions_group_data,
                "Hire_Date": hire_date,
                "Original_Hire_Date": original_hire_date,
                "Termination_Reason": termination_reason,
                "termination_date": termination_date,
                "termination_regret": termination_regret,
                "Termination_Category": termination_category,
                "Worker": worker,
                main_job_tag: job_history,
            }

            job_records.append(record)

        return job_records
