from app.models import TimeClock
from datetime import datetime, date
import calendar

def calculate_monthly_hours(user_id, year, month):
    """
    Calcule le total des heures travaillées par un employé 
    pendant un mois donné en fonction de ses pointages IN/OUT.
    """
    
    # Premier et dernier jour du mois
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    # Récupérer tous les pointages du mois pour cet utilisateur, triés chronologiquement
    clocks = TimeClock.query.filter(
        TimeClock.user_id == user_id,
        TimeClock.timestamp >= start_date,
        TimeClock.timestamp <= end_date
    ).order_by(TimeClock.timestamp.asc()).all()
    
    total_seconds = 0
    current_in = None
    
    for clock in clocks:
        if clock.action_type == 'IN':
            current_in = clock.timestamp
        elif clock.action_type == 'OUT' and current_in:
            # On calcule la durée de la session
            duration = clock.timestamp - current_in
            total_seconds += duration.total_seconds()
            current_in = None # Reset pour la prochaine session
            
    # Traiter si l'employé a un "IN" sans "OUT" le dernier jour (Pointage non cloturé)
    # Dans ce cas, on l'ignore ou on force l'heure actuelle si aujourd'hui
    if current_in and current_in.date() == date.today():
         duration = datetime.now() - current_in
         total_seconds += duration.total_seconds()
         
    total_hours = total_seconds / 3600.0
    return round(total_hours, 2)
