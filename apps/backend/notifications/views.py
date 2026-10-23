from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from config.api import ErrorSerializer

from .serializers import UnsubscribeSerializer
from .tokens import InvalidUnsubscribeToken, user_id_from_token


class InvalidToken(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_token"
    default_detail = "This unsubscribe link is not valid. Change the setting on your account page."


class UnsubscribeView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        operation_id="email_unsubscribe",
        tags=["notifications"],
        request=UnsubscribeSerializer,
        parameters=[
            OpenApiParameter(
                "token",
                str,
                required=False,
                description="The same token as the body field; mail clients put it in the URL.",
            )
        ],
        responses={204: OpenApiResponse(description="Unsubscribed."), 400: ErrorSerializer},
        description=(
            "Turns the Thursday matchday email off for the token's user. Also the target of the "
            "`List-Unsubscribe-Post` one-click request, which sends the token in the query string."
        ),
    )
    def post(self, request: Request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        token = body.get("token") or request.query_params.get("token")
        serializer = UnsubscribeSerializer(data={"token": token} if token else {})
        serializer.is_valid(raise_exception=True)
        try:
            user_id = user_id_from_token(serializer.validated_data["token"])
        except InvalidUnsubscribeToken as error:
            raise InvalidToken from error
        UserProfile.objects.filter(user_id=user_id).update(email_opt_in=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
