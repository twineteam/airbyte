import base64
import logging
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.call_rate import APIBudget
from airbyte_cdk.sources.streams.http import HttpStream

from .utils.requests import WorkdayRequest

logger = logging.getLogger(__name__)


_INCOMING_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class KnoeticWorkdayStream(HttpStream, ABC):
    """
    Each stream should extend this class (or another abstract subclass of it) to specify behavior unique to that stream.

    Typically for REST APIs each stream corresponds to a resource in the API. For example:

    if the API contains the endpoints
        - POST Human_Resources/37.2

    then you should have these classes:
    - `class KnoeticWorkdayStream(HttpStream, ABC)` which is the current class
    - `class IncrementalKnoeticWorkdayStream(KnoeticWorkdayStream, ABC)` contains behavior to pull data incrementally for workers using `Human_Resources/37.2`
    - `class Workers(KnoeticWorkdayStream)` contains behavior to pull data for workers using `Human_Resources/37.2`
    - `class WorkerDetails(KnoeticWorkdayStream)` contains behavior to pull data for worker details using `Human_Resources/37.2`
    - `class WorkerDetailsHistory(IncrementalKnoeticWorkdayStream)` contains behavior to pull data for worker details history using `Human_Resources/37.2`
    - `class WorkerDetailsPhoto(KnoeticWorkdayStream)` contains behavior to pull data for worker details photo using `Human_Resources/37.2`
    - `class OrganizationHierarchies(KnoeticWorkdayStream)` contains behavior to pull data for organization hierarchies using `Human_Resources/37.2`
    - `class Ethnicities(KnoeticWorkdayStream)` contains behavior to pull data for ethnicities using `Human_Resources/37.2`
    - `class GenderIdentities(KnoeticWorkdayStream)` contains behavior to pull data for gender identities using `Human_Resources/37.2`
    - `class Locations(KnoeticWorkdayStream)` contains behavior to pull data for locations using `Human_Resources/37.2`
    - `class JobProfiles(KnoeticWorkdayStream)` contains behavior to pull data for job profiles using `Human_Resources/37.2`
    - `class SexualOrientations(KnoeticWorkdayStream)` contains behavior to pull data for sexual orientations using `Human_Resources/37.2`

    if the API contains the endpoints
        - POST Staffing/37.2

    then you should have these classes:
    - `class Positions(KnoeticWorkdayStream)` contains behavior to pull data for positions using `Staffing/37.2`

    if the API contains the endpoints
        - POST Integrations/37.2

    then you should have these classes:
    - `class References(KnoeticWorkdayStream)` contains behavior to pull data for reference types using `Integrations/37.2`

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
        *,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
        web_service: str = "Human_Resources",
    ):
        super().__init__(api_budget)
        self.api_version = "37.2"
        self.web_service = web_service
        self._cursor_field = "Last_Modified"
        self.tenant = tenant
        self.url = url
        self.username = username
        self.password = password
        self.workday_request = workday_request
        self.page = page
        self.per_page = per_page

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
        
        # No need for a next page token if there is only one page
        return None

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        return f"{self.tenant}/{self.web_service}/{self.api_version}"


class IncrementalKnoeticWorkdayStream(KnoeticWorkdayStream, ABC):
    """
    This class implements an incremental Workday stream based on an effective
    date as the cursor field. It is used primarily for initial full sync and
    incremental syncs thereafter.
    """
    state_checkpoint_interval = None

    def get_updated_state(self, current_stream_state: MutableMapping[str, Any], latest_record: Mapping[str, Any]) -> Mapping[str, Any]:
        state_value = max(
            current_stream_state.get(self.cursor_field, ""),
            latest_record.get(self.cursor_field, "")
        )
        return {self.cursor_field: state_value}


class Workers(KnoeticWorkdayStream):
    """
    Represents a stream of `worker` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """

        if next_page_token:
            self.page = next_page_token["page"]
        
        request_config = {
            "file_name": "workers.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:

        parsed_response = self.workday_request.parse_response(response, stream_name="workers")

        yield from parsed_response


class WorkerDetails(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        *,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        worker_ids: List[str],
    ):

        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
        )
        self.worker_ids = worker_ids
        self.current_worker_id = None

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any] | str | None:
        self.current_worker_id = stream_slice.get("worker_id")

        request_config = {
            "file_name": "worker_details.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
            "worker_id": self.current_worker_id,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:

        parsed_response = self.workday_request.parse_response(response, stream_name="worker_details")
        for record in parsed_response:
            yield record
    
    def stream_slices(self, **kwargs) -> Iterable[Optional[Mapping[str, Any]]]:
        return [{"worker_id": worker_id} for worker_id in self.worker_ids]


class WorkerDetailsHistory(IncrementalKnoeticWorkdayStream):
    primary_key = None
    cursor_field = "as_of_effective_date"

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        workers_data: List[Mapping[str, Any]] = [],
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
        )
        self.workers_data = workers_data

    def request_body_data(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> str:
        worker_id = stream_slice.get("Worker_ID")
        as_of_effective_date = stream_slice.get("as_of_effective_date")

        request_config = {
            "file_name": "worker_details_history.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
            "worker_id": worker_id,
            "as_of_effective_date": as_of_effective_date,
        }
        request_body = self.workday_request.construct_request_body(request_config)

        return request_body

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        parsed_response = self.workday_request.parse_response(response, stream_name="worker_details_history")
        for record in parsed_response:
            record["as_of_effective_date"] = stream_slice.get("as_of_effective_date")
            yield record

    def stream_slices(self, sync_mode: SyncMode, cursor_field: List[str] = None, stream_state: Mapping[str, Any] = None) -> Iterable[Optional[Mapping[str, Any]]]:
        slices = []
        for worker in self.workers_data:
            worker_id = worker.get("Worker_ID")
            original_hire_date = datetime.strptime(worker.get("Original_Hire_Date"), "%Y-%m-%d")
            termination_date = worker.get("Termination_Date")
            if termination_date:
                end_date = datetime.strptime(termination_date, "%Y-%m-%d")
            else:
                end_date = datetime.now()

            state_date = stream_state.get(self.cursor_field) if stream_state else original_hire_date
            current_date = max(state_date, original_hire_date)
            while current_date <= end_date:
                slices.append({"Worker_ID": worker_id, "as_of_effective_date": current_date.strftime("%Y-%m-%d")})
                current_date += timedelta(days=1)
        return slices


class WorkerDetailsPhoto(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        *,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        worker_ids: List[str],
    ):

        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
        )
        self.worker_ids = worker_ids
        self.current_worker_id = None

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any] | str | None:
        self.current_worker_id = stream_slice.get("worker_id")

        request_config = {
            "file_name": "worker_details_photo.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
            "worker_id": self.current_worker_id,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
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

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "organization_hierarchies.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="organization_hierarchies")
        return response_json


class Ethnicities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `ethnicities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "ethnicities.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="ethnicities")
        return response_json


class GenderIdentities(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `gender_identities` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "gender_identities.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="gender_identities")
        return response_json


class Locations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `locations` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "locations.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="locations")
        return response_json


class JobProfiles(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `job_profiles` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "job_profiles.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="job_profiles")
        return response_json


class Positions(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="Staffing",
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "positions.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)


    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="positions")
        return response_json


class SexualOrientations(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `positions` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
        )

    def request_body_data(
        self,
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        request_config = {
            "file_name": "sexual_orientations.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
        }
        return self.workday_request.construct_request_body(request_config)

    def parse_response(
        self,
        response: requests.Response,
        *,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="sexual_orientations")
        return response_json


class References(KnoeticWorkdayStream):
    """
    Represents a collection of streams of `references` data from the Knoetic Workday source.
    It inherits from the KnoeticWorkdayStream class.
    """

    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="Integrations",
        )
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
        stream_state: Mapping[str, Any] | None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Override to define the request body data for the request.
        """
        self.current_reference_type = stream_slice.get("reference_type")
        request_config = {
            "file_name": "references.xml",
            "tenant": self.tenant,
            "username": self.username,
            "password": self.password,
            "page": self.page,
            "per_page": self.per_page,
            "reference_subcategory_type": self.current_reference_type,
        }
        return self.workday_request.construct_request_body(request_config)

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
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        response_json = self.workday_request.parse_response(response, stream_name="references")
        for record in response_json:
            yield record


class BaseCustomReport(KnoeticWorkdayStream):
    primary_key = None

    def __init__(
        self,
        tenant: str,
        url: str,
        username: str,
        password: str,
        base_snapshot_report: str,
        workday_request: WorkdayRequest,
        page: int = 1,
        per_page: int = 200,
        api_budget: APIBudget | None = None,
        base_historical_report_compensation: Optional[str] = None,
        base_historical_report_job: Optional[str] = None,
    ):
        super().__init__(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            workday_request=workday_request,
            page=page,
            per_page=per_page,
            api_budget=api_budget,
            web_service="customreport2",
        )
        self.base_snapshot_report = base_snapshot_report
        self.base_historical_report_compensation = base_historical_report_compensation
        self.base_historical_report_job = base_historical_report_job

    @property
    def http_method(self) -> str:
        return "GET"

    def path(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
    ) -> str:
        report_name = stream_slice.get("report_name")
        format_type = stream_slice.get("format_type")

        url_query_char = "&" if "?" in report_name else "?"
        return f"customreport2/{self.tenant}/{self.username}/{report_name}{url_query_char}format={format_type}"

    def request_headers(
        self,
        *,
        stream_state: Mapping[str, Any] | None = None,
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
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
        stream_slice: Mapping[str, Any] | None = None,
        next_page_token: Mapping[str, Any] | None = None,
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
            worker_id = next((ref.get('#content') for ref in worker_reference_ids if ref.get('-type') == 'WID'), None)

            if worker_id:
                workers_data.append({
                    "Worker_ID": worker_id,
                    "Original_Hire_Date": worker.get("Original_Hire_Date"),
                    "Hire_Date": worker.get("Hire_Date"),
                    "Termination_Date": worker.get("Termination_Date"),
                })
        
        return workers_data


    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        """
        :param config: A Mapping of the user input configuration as defined in the connector spec.
        """

        tenant = config["tenant"]

        # url should end with a trailing slash
        url = config["url"]
        if not url.endswith("/"):
            url = f"{url}/"

        username = config["username"]
        password = config["password"]
        base_snapshot_report = config.get("base_snapshot_report")
        base_historical_report_compensation = config.get("base_historical_report_compensation")
        base_historical_report_job = config.get("base_historical_report_job")
        per_page = config.get("per_page", 200)

        workers_stream = Workers(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            per_page=per_page,
            workday_request=WorkdayRequest(),
        )

        workers_data = self.get_worker_info_for_substreams(workers_stream)
        worker_ids = [worker.get("Worker_ID") for worker in workers_data]

        worker_details_stream = WorkerDetails(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            per_page=per_page,
            workday_request=WorkdayRequest(),
            worker_ids=worker_ids,
        )

        worker_details_history_stream = WorkerDetailsHistory(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            per_page=per_page,
            workday_request=WorkdayRequest(),
            workers_data=workers_data,
        )

        worker_details_photo_stream = WorkerDetailsPhoto(
            tenant=tenant,
            url=url,
            username=username,
            password=password,
            per_page=per_page,
            workday_request=WorkdayRequest(),
            worker_ids=worker_ids,
        )

        return [
            workers_stream,
            worker_details_stream,
            worker_details_history_stream,
            worker_details_photo_stream,
            OrganizationHierarchies(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Ethnicities(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            GenderIdentities(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Locations(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            JobProfiles(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            Positions(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            SexualOrientations(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            References(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
            BaseCustomReport(
                tenant=tenant,
                url=url,
                username=username,
                password=password,
                base_snapshot_report=base_snapshot_report,
                base_historical_report_compensation=base_historical_report_compensation,
                base_historical_report_job=base_historical_report_job,
                per_page=per_page,
                workday_request=WorkdayRequest(),
            ),
        ]
