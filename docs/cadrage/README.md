# Cadrage du projet

Version publique des documents de cadrage ; certaines sections hors projet ont été retirées.

Documents de référence du pipeline SenFinance Microcrédit, dans l'ordre de lecture.

- [PRD_pipeline_IMF_SYSCOHADA.md](PRD_pipeline_IMF_SYSCOHADA.md) — PRD du projet : objectifs, périmètre, architecture, plan des phases.
- [P1_phase0_cadrage.md](P1_phase0_cadrage.md) — Phase 0 : plan de comptes, schéma en étoile, règles de mapping (D1 à D21), exemples chiffrés.
- [P1_phase2_cadrage.md](P1_phase2_cadrage.md) — Phase 2 : générateur de données fictives et anomalies injectées.
- [P1_phase3_cadrage.md](P1_phase3_cadrage.md) — Phase 3 : ingestion bronze incrémentale et idempotente (I1 à I14).
- [P1_phase4_cadrage.md](P1_phase4_cadrage.md) — Phase 4 : silver dbt (S1 à S15).
- [P1_phase5_cadrage.md](P1_phase5_cadrage.md) — Phase 5 : gold, dimensions, écritures et faits (G1 à G15).
- [P1_phase6_cadrage.md](P1_phase6_cadrage.md) — Phase 6 : marts, balances, états financiers, KPI, rapprochements (H1 à H12).
- [P1_phase7_cadrage.md](P1_phase7_cadrage.md) — Phase 7 : orchestration Airflow, gold « à date », contrôles et audit (J1 à J20).
- [P1_checklist_relecture_SFD.md](P1_checklist_relecture_SFD.md) — Points à faire vérifier par un professionnel des SFD sur le plan de comptes et le mapping.
- [P1_cas_chiffres_tests.md](P1_cas_chiffres_tests.md) — Cas chiffrés calculés à la main (écritures, balances, compte de résultat, rapprochements, bilan) : attendus des tests unitaires des marts.
- [P1_phase6_notes.md](P1_phase6_notes.md) — Phase 6 : notes de relecture (ordre d'imputation des remboursements, lot A).
