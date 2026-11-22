"""Orchestration du pipeline (phase 7) : commandes appelées par le DAG Airflow.

Ce paquet tourne dans le venv du projet et n'importe jamais Airflow. Contrat de sortie de
chaque commande (python -m orchestration <commande> --date AAAA-MM-JJ) :
  0 = succès (avertissement compris) ; 3 = échec de contrôle (bloquant, ne pas relancer) ;
  autre = erreur technique (relançable). La dernière ligne de stdout est un résumé JSON.
"""
