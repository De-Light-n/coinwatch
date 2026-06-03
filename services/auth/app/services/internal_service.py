from app.schemas.internal import Limits

def get_plan_limits(plan: str) -> Limits:
    plan = plan.lower() if plan else "free"
    
    if plan == "business":
        return Limits(
            max_watches=999999, 
            check_interval_seconds=60, 
            allowed_channels=["email", "telegram", "webhook"]
        )
    elif plan == "pro":
        return Limits(
            max_watches=50, 
            check_interval_seconds=300, 
            allowed_channels=["email", "telegram"]
        )
    else:
        # Default / free
        return Limits(
            max_watches=3, 
            check_interval_seconds=3600, 
            allowed_channels=["email"]
        )