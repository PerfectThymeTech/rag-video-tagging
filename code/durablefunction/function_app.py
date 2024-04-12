import json
import logging

import azure.durable_functions as df
import azure.functions as func
from bp_videoextraction import bp
from models.error import ErrorModel
from models.startworkflow import StartWorkflowRequest

# from newstagextraction.orchestration import bp_newstagextraction
from pydantic import ValidationError

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_functions(bp)
# app.register_functions(bp_newstagextraction)


@app.route(route="HttpTrigger")
def HttpTrigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    name = req.params.get("name")
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get("name")

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This HTTP triggered function executed successfully."
        )
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
            status_code=200,
        )


# # An HTTP-Triggered Function with a Durable Functions Client binding
# @app.function_name("StartWorkflow")
# @app.route(route="startWorkflow")
# @app.durable_client_input(client_name="client")
# async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
#     try:
#         # Parse body
#         payload = json.loads(req.get_body().decode())
#         payload_obj: StartWorkflowRequest = StartWorkflowRequest.model_validate(payload)

#         # Start orchestrator
#         instance_id = await client.start_new(
#             payload_obj.orchestrator_workflow_name.value, client_input=payload
#         )
#         response = client.create_check_status_response(req, instance_id)
#     except ValidationError as e:
#         logging.error(f"Validation Error occured for task hub payload: {e}")
#         return func.HttpResponse(
#             body=ErrorModel(
#                 error_code=10,
#                 error_message="Provided input is not following the expected data model",
#                 error_details=json.loads(e.json()),
#             ).model_dump_json(),
#             status_code=422,
#         )
#     return response
