# Mockup UX chef d'atelier

Mockup HTML statique pour valider l'UX décisionnelle de la SaaS d'ordonnancement
auprès des design partners **avant** d'investir dans la stack frontend (Phase 5
= Next.js + shadcn).

> **Statut** : jetable. Quand Phase 5.1 démarre, ce mockup est archivé. Les
> apprentissages se transfèrent dans le scaffolding Next.js, le code HTML lui-
> même non.

## Comment ouvrir

```bash
# Depuis ce dossier
python3 -m http.server 8080
# puis ouvrir http://localhost:8080/index.html
```

Ou simplement double-cliquer sur `index.html` dans un navigateur.

Aucune build, aucune dépendance npm. Tailwind est chargé via CDN, les données
sont en JS dans `data.js`.

## Les 8 écrans

### Onboarding (3 écrans — J0 install / calibration)

| Fichier | Écran | Ce qu'il démontre |
|---------|-------|-------------------|
| `onboarding-1-atelier.html` | **Configuration atelier** | Questionnaire arborescent visible (15 essentielles + 3 contextuelles selon réponses), aperçu du parcours à droite, message « onboarding progressif » (pas tout au J0). Question pilote : setup-dependent. |
| `onboarding-2-import.html` | **Import CSV ERP** | Upload + auto-détection colonnes, 3 niveaux d'anomalies (3 certaines bloquantes / 8 probables / 2 surprenantes), fuzzy matching client, fix in-place ou exclusion. |
| `onboarding-3-first-plan.html` | **Préférences NL & 1er solve** | Récap config, textarea soft constraints en langage naturel, **live parsing** en chips typées (4 règles détectées dont 1 contrainte dure repérée par le mot « jamais »), bouton « générer mon premier planning » avec trace circuit breaker → simulation → score. |

### Quotidien chef d'atelier (5 écrans — usage J+1 et après)

| Fichier | Écran | Ce qu'il démontre |
|---------|-------|-------------------|
| `index.html` | **Dashboard** | KPI jour, alertes (3 sévérités), aperçu Gantt 7j, raccourcis vers les actions clés. C'est ce que Pierre voit en arrivant à 7h45. |
| `gantt.html` | **Planning interactif** | Gantt par machine × jour, codes couleur Tier 1/2/3 par client, zone freeze 8h glissantes, click sur OF → panneau latéral avec actions (geler, expliquer, reporter). |
| `conversation.html` | **Demander une modification** | Chat NL « priorité 1 sur Safran », preview impact à droite (diff métriques + OF impactés), **carte de validation systématique** (rien n'est appliqué sans ✓). |
| `infeasibility.html` | **Diagnostic INFEASIBLE** | Bandeau rouge, trace transparente du circuit breaker (3 retries), 2 causes MIS expliquées en NL, actions correctives cliquables, mode dégradé optionnel. |
| `versioning.html` | **Historique** | Timeline versions, diff métriques v22→v23, liste des changements, rollback avec carte de validation. |

## Données factices

Atelier **« Mécanique Précision SAS »** (Saint-Étienne, EN 9100 + IATF 16949) —
volontairement crédible pour qu'un DP puisse projeter mentalement son propre
atelier.

- 8 machines : 5 tours CN, 2 fraiseuses 5 axes, 1 rectifieuse
- 25 OF sur la semaine S20 (12-16 mai 2026)
- 4 clients couvrant les 3 tiers : Safran (T1), Stellantis/Bosch (T2), ProtoLab (T3)
- 1 scénario INFEASIBLE pilote (maintenance CN-3 + 12 OF Stellantis qui arrivent)
- 4 versions historisées dans `versioning.html`

Toutes les données sont dans `data.js`. Pour itérer, modifier ce fichier
suffit.

## Principes UX que le mockup illustre

Tirés de `specs-fonctionnelles-v3.md` :

1. **Le chef d'atelier garde toujours le dernier mot** — la carte de
   validation jaune apparaît avant toute application de modification
   (conversation + versioning).
2. **Score de confiance visible** — affiché sur le dashboard et dans la
   conversation, avec tooltip explicatif.
3. **Trust layer transparent** — la page infaisabilité montre la trace des
   3 tentatives du circuit breaker, pas juste l'erreur.
4. **Tier-pondération visualisée** — couleurs cohérentes Safran/Stellantis/
   ProtoLab partout (T1 wine, T2 orange, T3 slate).
5. **MIS rendu actionable** — chaque cause d'infaisabilité a une action
   corrective concrète attachée (« reporter la maintenance », « décaler l'OF »).
6. **Versioning auditable** — chaque modification crée une version, le
   rollback ne supprime pas l'historique.

## Ce que le mockup ne couvre PAS (volontairement)

- **Mini-questionnaires contextuels** post-J0 (les 5-6 questions qui
  reviennent à 4 semaines avec données réelles) — implicite dans le
  message d'onboarding-1, à mocker si retours DP demandent un démo.
- **Mobile / PWA opérateur** (Phase 6) — hors scope de ce mockup chef
  d'atelier.
- **Multi-tenant / auth** — non pertinent pour valider l'UX décisionnelle.
- **Vue famille / clustering visuel** des pièces (« voici les 8 familles
  détectées dans tes 200 pièces ») — pertinent pour Phase 1.7 démo,
  ajouter si besoin.

## Comment l'utiliser avec un DP

Deux parcours selon le moment de la conversation :

### Parcours 1 — « Comment je m'installe ? » (onboarding)

Réponse à la question critique sur le pricing 5-12K€ d'install (specs V3 §1).
1. `onboarding-1-atelier.html` : « 15 questions essentielles, le reste vient
   sur 4-6 semaines avec tes données réelles »
2. `onboarding-2-import.html` : « tu pousses ton export ERP, le système
   trouve 13 trucs bizarres, on les corrige ensemble en 5 min »
3. `onboarding-3-first-plan.html` : « tu décris en français ce qui te tient
   à cœur, le système traduit en règles » + premier solve avec trace trust layer
4. Enchaîner sur `gantt.html` (« voici ton premier planning »)

### Parcours 2 — « C'est quoi mon quotidien ? » (5 écrans déjà existants)

1. `index.html` : « voici ce que tu vois lundi matin »
2. Click « Replanifier » → emmène sur conversation
3. `conversation.html` : « priorité 1 sur Safran » → montre la carte de validation
4. `gantt.html` : zone freeze, click un OF
5. `infeasibility.html` : « si tu ajoutes 12 OF Stellantis et CN-3 maintenance
   vendredi, voici ce qui se passe »
6. `versioning.html` : « tout est tracé, rollback possible »

**Après la session DP** : récolte 3 questions par écran (« est-ce que tu
cliquerais ici ? », « est-ce que ce truc t'aiderait ? », « qu'est-ce qui
manque ? »). Itère sur les fichiers HTML.

## Narratif à dérouler

> Lundi 12 mai 2026, 7h45. Pierre Marchand, chef d'atelier de Mécanique
> Précision SAS, ouvre l'écran. Trois alertes l'attendent : un OF Safran
> avec 30 min de marge, une maintenance CN-3 vendredi, 12 nouveaux OF
> Stellantis arrivés ce matin.
>
> Pierre a une visite Safran jeudi : il tape *« priorité 1 sur Safran cette
> semaine »*. Le système lui montre l'impact (5 OF Stellantis reculent de
> 1.5j en moyenne, aucun conflit, makespan stable). Pierre valide.
>
> Mais le système retourne INFEASIBLE : la maintenance CN-3 vendredi bloque
> 2 OF Safran avec deadline lundi. Le système propose : reporter la
> maintenance, ou décaler l'OF Stellantis-0892 trop long. Pierre choisit la
> 2ᵉ option, contacte Stellantis qui accepte.
>
> 7h58, planning v23 actif. Pierre lance la production. À 17h, il consulte
> l'historique pour voir ce qui a changé depuis vendredi : timeline,
> métriques, rollback dispo si besoin.

C'est le PMF que ce mockup teste.
