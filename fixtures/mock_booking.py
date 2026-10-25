"""Controlled example: deliberately NOT a real calendar integration."""
def book_appointment(request):
    return {"status": "confirmed", "booking_id": "mock-001"}
