"""
ArchitectOS API Gateway v1

Responsible for:
- receiving requests
- forwarding to Chat Runtime
- returning normalized responses

No AI logic here.
"""


from core.api.schemas import (
    ChatRequest,
    ChatResponse
)


class APIGateway:


    def __init__(
        self,
        chat_runtime
    ):

        self.chat_runtime = chat_runtime


    def chat(
        self,
        request: ChatRequest
    ) -> ChatResponse:


        result = self.chat_runtime.process(
            message=request.message,
            session_id=request.session_id
        )


        return ChatResponse(

            status="success",

            session_id=request.session_id,

            response=result.get(
                "response",
                ""
            ),

            tool=result.get(
                "tool"
            ),

            metadata=result

        )