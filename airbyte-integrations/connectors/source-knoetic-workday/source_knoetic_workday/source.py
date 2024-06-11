import base64
import logging
import time
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.models import AirbyteMessage, SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import IncrementalMixin, Stream
from airbyte_cdk.sources.streams.call_rate import APIBudget
from airbyte_cdk.sources.streams.http import HttpStream

from .utils.requests import WorkdayRequest

logger = logging.getLogger(__name__)


class KnoeticWorkdayStream(HttpStream, ABC):
    """
    Each stream should extend this class (or another abstract subclass of it) to specify behavior unique to that stream.

    Typically for REST APIs each stream corresponds to a resource in the API. For example:

    if the API contains the endpoints
        - POST Human_Resources/37.2

    then you should have these classes:
    - `class KnoeticWorkdayStream(HttpStream, ABC)` which is the current class
    - `class IncrementalKnoeticWorkdayStream(KnoeticWorkdayStream, ABC)` contains behavior to pull
    data incrementally for workers using `Human_Resources/37.2`
    - `class Workers(KnoeticWorkdayStream)` contains behavior to pull data for workers using `Human_Resources/37.2`
    - `class WorkerDetails(KnoeticWorkdayStream)` contains behavior to pull data for worker details
    using `Human_Resources/37.2`
    - `class WorkerDetailsHistory(IncrementalKnoeticWorkdayStream)` contains behavior to pull data
    for worker details history using `Human_Resources/37.2`
    - `class WorkerDetailsPhoto(KnoeticWorkdayStream)` contains behavior to pull data for worker
    details photo using `Human_Resources/37.2`
    - `class OrganizationHierarchies(KnoeticWorkdayStream)` contains behavior to pull data for organization
    hierarchies using `Human_Resources/37.2`
    - `class Ethnicities(KnoeticWorkdayStream)` contains behavior to pull data for ethnicities using
    `Human_Resources/37.2`
    - `class GenderIdentities(KnoeticWorkdayStream)` contains behavior to pull data for gender
    identities using `Human_Resources/37.2`
    - `class Locations(KnoeticWorkdayStream)` contains behavior to pull data for locations using `Human_Resources/37.2`
    - `class JobProfiles(KnoeticWorkdayStream)` contains behavior to pull data for job profiles
    using `Human_Resources/37.2`
    - `class SexualOrientations(KnoeticWorkdayStream)` contains behavior to pull data for sexual
    orientations using `Human_Resources/37.2`

    if the API contains the endpoints
        - POST Staffing/37.2

    then you should have these classes:
    - `class Positions(KnoeticWorkdayStream)` contains behavior to pull data for positions using `Staffing/37.2`

    if the API contains the endpoints
        - POST Integrations/37.2

    then you should have these classes:
    - `class References(KnoeticWorkdayStream)` contains behavior to pull data for reference types
    using `Integrations/37.2`

    if the API contains the endpoints
        - GET customreport2

    then you should have these classes:
    - `class BaseCustomReport(KnoeticWorkdayStream)` contains behavior to pull data for:
        - a base snapshot report using `customreport2`
        - a base historical report for compensation using `customreport2`
        - a base historical report for job using `customreport2`

    See the reference docs for the full list of configurable options.
    """

    def __init__(
        self,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
        file_name: str,
        stream_name: str,
        api_budget: APIBudget = None,
    ):
        super().__init__(api_budget)
        self.api_version = config.get("api_version", "37.2")
        self.web_service = config.get("web_service", "Human_Resources")
        self.tenant = config.get("tenant")
        self.url = config.get("url")
        self.username = config.get("username")
        self.password = config.get("password")
        self.workday_request = workday_request
        self.per_page = config.get("per_page", 200)
        self.page = 1
        self.file_name = file_name
        self.stream_name = stream_name

    @property
    def http_method(self) -> str:
        """
        :return str: The HTTP method for the request. Default is "GET".
        """
        return "POST"

    @property
    def url_base(self) -> str:
        """
        :return The base URL for the API.
        """

        return f"{self.url}"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        """
        :param response: the most recent response from the API
        :return If there is another page in the result, a mapping (e.g: dict) containing information
        needed to query the next page in the response. If there are no more pages in the result, return None.
        """

        response_text = response.text

        import xml.etree.ElementTree as ET

        root = ET.fromstring(response_text)
        ns = {"wd": "urn:com.workday/bsvc"}

        # Find the current page and total pages
        current_page_elem = root.find(".//wd:Page", ns)
        total_pages_elem = root.find(".//wd:Total_Pages", ns)

        if (
            current_page_elem is not None
            and current_page_elem.text is not None
            and total_pages_elem is not None
            and total_pages_elem.text is not None
        ):
            current_page = int(current_page_elem.text)
            total_pages = int(total_pages_elem.text)

            if current_page < total_pages:
                next_page = current_page + 1
                return {"page": next_page}

        return None

    def request_body_data(  # type: ignore
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
        **kwargs,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        page = next_page_token["page"] if next_page_token else 1

        request_config = {
            "file_name": self.file_name,
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "per_page": self.per_page,
            "page": page,
            **kwargs,
        }

        return self.workday_request.construct_request_body(**request_config)

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> str:
        return f"{self.tenant}/{self.web_service}/{self.api_version}"

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:

        parsed_response = self.workday_request.parse_response(response, stream_name=self.stream_name)

        yield from parsed_response


class Workers(KnoeticWorkdayStream):
    """
    Represents a stream of `worker` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest, api_budget: APIBudget = None):
        super().__init__(
            config=config,
            workday_request=workday_request,
            api_budget=api_budget,
            file_name="workers.xml",
            stream_name="workers",
        )


class WorkerDetails(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
        worker_ids: List[str],
        api_budget: APIBudget = None,
    ):
        super().__init__(
            config=config,
            workday_request=workday_request,
            api_budget=api_budget,
            file_name="worker_details.xml",
            stream_name="worker_details",
        )
        self.worker_ids = worker_ids

    def request_body_data(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
        **kwargs,
    ) -> str:
        if stream_slice:
            self.current_worker_id = stream_slice["worker_id"]

        return super().request_body_data(
            stream_state, stream_slice, next_page_token, worker_id=self.current_worker_id, **kwargs
        )

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        return [{"worker_id": worker_id} for worker_id in self.worker_ids]


class WorkerDetailsHistory(KnoeticWorkdayStream, IncrementalMixin):
    primary_key = "id"
    state_checkpoint_interval = 100
    cursor_field = "state"

    def __init__(
        self,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
        workers_data: List[Mapping[str, Any]],
    ):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="worker_details.xml",
            stream_name="worker_details",
        )
        self.workers_data = workers_data
        self._cursor_value = None

    @property
    def state(self) -> Mapping[str, Any]:
        return {self.cursor_field: str(self._cursor_value)}

    @state.setter
    def state(self, value: Mapping[str, Any]):
        print("value", value)
        print("self._cursor_value", self._cursor_value)
        time.sleep(5)
        if not self._cursor_value:
            self._cursor_value = value
        else:
            self._cursor_value = self._cursor_value.update(value)

    def request_body_data(  # type: ignore
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
        **kwargs,
    ) -> str:
        if stream_slice:
            worker_id = stream_slice["Worker_ID"]
            as_of_effective_date = stream_slice["as_of_effective_date"]

        return super().request_body_data(
            stream_state,
            stream_slice,
            next_page_token,
            worker_id=worker_id,
            as_of_effective_date=as_of_effective_date,
            **kwargs,
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        parsed_response = self.workday_request.parse_response(response, stream_name="worker_details_history")
        for record in parsed_response:
            record["as_of_effective_date"] = stream_slice.get("as_of_effective_date")
            yield record

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: List[str] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        stream_state: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any] | AirbyteMessage]:
        for record in super().read_records(sync_mode, cursor_field, stream_slice, stream_state):
            if self._cursor_value:
                self._cursor_value.update({record["Worker_Data"]["Worker_ID"]: record["as_of_effective_date"]})
            else:
                self._cursor_value = {record["Worker_Data"]["Worker_ID"]: record["as_of_effective_date"]}
            yield record

    def stream_slices(
        self,
        *,
        sync_mode: SyncMode,
        cursor_field: List[str] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:

        min_original_hire_date = min(
            datetime.strptime(worker.get("Original_Hire_Date"), "%Y-%m-%d") for worker in self.workers_data
        )
        state_date = stream_state.get(self.cursor_field) if stream_state else min_original_hire_date

        slices = []
        for worker in self.workers_data:
            worker_id = worker.get("Worker_ID")
            original_hire_date = datetime.strptime(worker.get("Original_Hire_Date"), "%Y-%m-%d")

            start_date = max(state_date, original_hire_date)

            termination_date = worker.get("Termination_Date")
            if termination_date:
                end_date = datetime.strptime(termination_date, "%Y-%m-%d")
            else:
                end_date = datetime.now()

            start_date = end_date - timedelta(days=3)
            while start_date <= end_date:
                slices.append({"Worker_ID": worker_id, "as_of_effective_date": start_date.strftime("%Y-%m-%d")})
                start_date += timedelta(days=1)

        return slices


class WorkerDetailsPhoto(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
        worker_ids: List[str],
    ):

        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="worker_details_photo.xml",
            stream_name="worker_details_photo",
        )
        self.worker_ids = worker_ids
        self.current_worker_id = None

    def request_body_data(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
        **kwargs,
    ) -> str:
        if stream_slice:
            self.current_worker_id = stream_slice["worker_id"]

        return super().request_body_data(
            stream_state, stream_slice, next_page_token, worker_id=self.current_worker_id, **kwargs
        )

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        parsed_response = self.workday_request.parse_response(response, stream_name="worker_details_photo")
        for record in parsed_response:
            yield record

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        return [{"worker_id": worker_id} for worker_id in self.worker_ids]


class OrganizationHierarchies(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `organization hierarchies` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            stream_name="organization_hierarchies",
            file_name="organization_hierarchies.xml",
        )


class Ethnicities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `ethnicities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="ethnicities.xml",
            stream_name="ethinicities",
        )


class GenderIdentities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `gender_identities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="gender_identities.xml",
            stream_name="gender_identities",
        )


class Locations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `locations` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="locations.xml",
            stream_name="locations",
        )


class JobProfiles(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `job_profiles` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="job_profiles.xml",
            stream_name="job_profiles",
        )


class Positions(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="positions.xml",
            stream_name="positions",
        )


class SexualOrientations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(self, config: Mapping[str, Any], workday_request: WorkdayRequest):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="sexual_orientations.xml",
            stream_name="sexual_orientations",
        )


class References(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `references` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
    ):
        super().__init__(
            config=config,
            workday_request=workday_request,
            file_name="references.xml",
            stream_name="references",
        )
        self.web_service = "Integrations"
        self.reference_types = [
            "Contingent_Worker_Type_ID",
            "Employee_Type_ID",
            "Ethnicity_ID",
            "Event_Classification_Subcategory_ID",
            "Gender_Code",
            "Job_Category_ID",
            "Job_Family_ID",
            "Job_Level_ID",
            "Management_Level_ID",
            "Marital_Status_ID",
            "Organization_Subtype_ID",
            "Organization_Type_ID",
        ]
        self.current_reference_type = None

    def request_body_data(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
        **kwargs,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        self.current_reference_type = stream_slice["reference_type"]
        request_config = {
            "file_name": "references.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
            "reference_subcategory_type": self.current_reference_type,
        }
        return self.workday_request.construct_request_body(**request_config, **kwargs)

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        """
        Override to provide slices for each reference type.
        """
        return [{"reference_type": ref_type} for ref_type in self.reference_types]

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="references")
        for record in response_json:
            yield record


class BaseCustomReport(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        config: Mapping[str, Any],
        workday_request: WorkdayRequest,
        base_snapshot_report: Optional[str] = None,
        base_historical_report_compensation: Optional[str] = None,
        base_historical_report_job: Optional[str] = None,
    ):
        super().__init__(config=config, workday_request=workday_request, file_name=None, stream_name=None)
        self.web_service = "customreport2"
        self.base_snapshot_report = base_snapshot_report
        self.base_historical_report_compensation = base_historical_report_compensation
        self.base_historical_report_job = base_historical_report_job

    @property
    def http_method(self) -> str:
        return "GET"

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> str:
        report_name = stream_slice.get("report_name")
        format_type = stream_slice.get("format_type")

        url_query_char = "&" if "?" in report_name else "?"
        return f"customreport2/{self.tenant}/{self.username}/{report_name}{url_query_char}format={format_type}"

    def request_headers(
        self,
        *,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Mapping[str, Any]:
        format_type = "application/xml" if stream_slice.get("format_type") == "xml" else "text/csv"
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
        return {"Content-Type": "application/json", "Accept": format_type, "Authorization": f"Basic {token}"}

    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        slices = []
        if self.base_snapshot_report:
            slices.append({"report_name": self.base_snapshot_report, "format_type": "csv"})
        if self.base_historical_report_compensation:
            slices.append({"report_name": self.base_historical_report_compensation, "format_type": "xml"})
        if self.base_historical_report_job:
            slices.append({"report_name": self.base_historical_report_job, "format_type": "xml"})
        return slices

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        if stream_slice.get("format_type") == "xml":
            if stream_slice.get("report_name") == self.base_historical_report_compensation:
                response_json = self.workday_request.parse_response(
                    response, stream_name="base_historical_report_compensation"
                )
                for record in response_json:
                    yield record

            if stream_slice.get("report_name") == self.base_historical_report_job:
                response_json = self.workday_request.parse_response(response, stream_name="base_historical_report_job")
                for record in response_json:
                    yield record

        else:
            response_json = self.workday_request.parse_response(response, stream_name="base_snapshot_report")
            for record in response_json:
                yield record


class SourceKnoeticWorkday(AbstractSource):
    def check_connection(self, logger, config) -> Tuple[bool, any]:
        """
        TODO: Implement a connection check to validate that the user-provided config can be used to
        connect to the underlying API

        See `https://github.com/airbytehq/airbyte/blob/master/airbyte-integrations/
        connectors/source-stripe/source_stripe/source.py#L232` for an example.

        :param config:  the user-input config object conforming to the connector's spec.yaml
        :param logger:  logger object
        :return Tuple[bool, any]: (True, None) if the input config can be used to connect to the API
            successfully, (False, error) otherwise.
        """
        return True, None

    def get_worker_info_for_substreams(self, workers_stream: Workers):
        workers_data = []
        for worker in workers_stream.read_records(sync_mode="full_refresh"):
            worker_reference_ids = worker.get("Worker_Reference", {}).get("ID", [])
            worker_id = next((ref.get("#content") for ref in worker_reference_ids if ref.get("-type") == "WID"), None)

            if worker_id:
                workers_data.append(
                    {
                        "Worker_ID": worker_id,
                        "Original_Hire_Date": worker.get("Original_Hire_Date"),
                        "Hire_Date": worker.get("Hire_Date"),
                        "Termination_Date": worker.get("Termination_Date"),
                    }
                )

        return workers_data

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """

        workday_request = WorkdayRequest()

        # workers_stream = Workers(config=config, workday_request=workday_request)

        # workers_data = self.get_worker_info_for_substreams(workers_stream)
        workers_data = [
            {
                "Worker_ID": "65fd8bbd9d35100651cdc72f47ca0000",
                "Original_Hire_Date": "2012-05-31",
                "Hire_Date": "2012-05-31",
                "Termination_Date": None,
            },
            {
                "Worker_ID": "65fd8bbd9d35100651cde2c918f30001",
                "Original_Hire_Date": "2013-08-14",
                "Hire_Date": "2013-08-14",
                "Termination_Date": None,
            },
            {
                "Worker_ID": "65fd8bbd9d35100651cdef63f5820000",
                "Original_Hire_Date": "2013-09-01",
                "Hire_Date": "2013-09-01",
                "Termination_Date": None,
            },
            {
                "Worker_ID": "65fd8bbd9d35100651cdfb6303620001",
                "Original_Hire_Date": "2013-09-01",
                "Hire_Date": "2013-09-01",
                "Termination_Date": None,
            },
            {
                "Worker_ID": "65fd8bbd9d35100651ce076303c00000",
                "Original_Hire_Date": "2014-06-09",
                "Hire_Date": "2014-06-09",
                "Termination_Date": None,
            },
        ]

        worker_ids = [worker["Worker_ID"] for worker in workers_data]

        return [
            Workers(config=config, workday_request=workday_request),
            WorkerDetails(config=config, workday_request=workday_request, worker_ids=worker_ids),
            WorkerDetailsHistory(config=config, workday_request=workday_request, workers_data=workers_data),
            WorkerDetailsPhoto(config=config, workday_request=workday_request, worker_ids=worker_ids),
            OrganizationHierarchies(config=config, workday_request=workday_request),
            Ethnicities(config=config, workday_request=workday_request),
            GenderIdentities(config=config, workday_request=workday_request),
            Locations(config=config, workday_request=workday_request),
            JobProfiles(config=config, workday_request=workday_request),
            SexualOrientations(config=config, workday_request=workday_request),
            References(config=config, workday_request=workday_request),
            BaseCustomReport(config=config, workday_request=workday_request),
        ]
