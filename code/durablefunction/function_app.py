import azure.durable_functions as df
import azure.functions as func
from models.start_workflow import StartWorkflowRequest
from pydantic import TypeAdapter
from shared.config import settings
from videoextraction.orchestration import bp as bp_videoextraction

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_functions(bp_videoextraction)


# An HTTP-Triggered Function with a Durable Functions Client binding
@app.function_name("StartWorkflow")
@app.route(route="startWorkflow")
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    # Parse body
    body: StartWorkflowRequest = TypeAdapter(StartWorkflowRequest).validate_json(
        req.get_json()
    )

    # Start orchestrator
    instance_id = await client.start_new(body.orchestrator_workflow_name)
    response = client.create_check_status_response(req, instance_id)
    return response
