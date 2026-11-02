from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Standardized API error envelope matching Avenor frontend contracts:
    {
        "success": False,
        "message": "Error description",
        "errors": { "field": ["detail"] }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        errors = {}
        message = "A validation or request error occurred."

        if isinstance(response.data, dict):
            if 'detail' in response.data:
                message = str(response.data['detail'])
            else:
                errors = response.data
                message = "Validation failed. Please correct the errors."
        elif isinstance(response.data, list):
            errors = {'non_field_errors': response.data}
            message = "Validation failed."
        else:
            message = str(response.data)

        custom_data = {
            'success': False,
            'message': message,
            'errors': errors,
        }
        response.data = custom_data
    else:
        logger.exception("Unhandled server exception: %s", exc)
        response = Response(
            {
                'success': False,
                'message': 'An unexpected internal server error occurred.',
                'errors': {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response
