# Spec produit V3 — SaaS d'ordonnancement IA pour la sous-traitance mécanique PME

> Document de référence fonctionnel
> Version 3 — document de travail
> Cible : sous-traitance mécanique de précision, PME 10-50 personnes

---

## Table des matières

1. [Positionnement produit](#1-positionnement-produit)
2. [Architecture technique (vue fonctionnelle)](#2-architecture-technique-vue-fonctionnelle)
3. [Le module Data Quality](#3-le-module-data-quality)
4. [Le questionnaire arborescent conditionnel](#4-le-questionnaire-arborescent-conditionnel)
5. [Périmètre V1 — discipline du wedge](#5-périmètre-v1--discipline-du-wedge)
6. [Le trust layer](#6-le-trust-layer--le-chantier-principal-du-produit)
7. [Modélisation des points sensibles](#7-modélisation-des-points-sensibles)
8. [Business model et coûts](#8-business-model-et-coûts)
9. [Trajectoire et go-to-market](#9-trajectoire-et-go-to-market)
10. [Stratégie de défensibilité 3-5 ans](#10-stratégie-de-défensibilité-3-5-ans)
11. [Critères go/no-go](#11-critères-gono-go-à-chaque-étape)
12. [Évolution depuis la V2](#12-ce-qui-change-par-rapport-à-la-v2)

---

## 1. Positionnement produit

Tu construis un APS (Advanced Planning & Scheduling) vertical pour les PME industrielles de sous-traitance mécanique de précision, avec une couche d'intelligence artificielle utilisée de manière disciplinée et opinionée. La promesse n'est pas révolutionnaire dans sa forme — c'est un planning d'atelier — mais elle l'est dans son économie : tu rends accessible à 800-2500€/mois ce qui coûte aujourd'hui 30-200K€ et 6 mois de déploiement chez les acteurs établis.

**Positionnement principal :**
> *"L'ordonnancement industriel intelligent pour les ateliers qui n'ont pas le temps d'attendre 6 mois"*

Cette formulation assume la valeur, cadre les attentes (rapidité, accessibilité), et évite le piège de la comparaison frontale avec Ortems/Asprova qui déclencherait des attentes de feature parity intenables.

**Sous-positionnement complémentaire :**
> *"Avec une IA qui sait travailler avec vous et qui sait dire quand elle ne sait pas"*

La seconde partie est aussi importante que la première — c'est ce qui te distingue des concurrents qui vendent leur IA comme infaillible et qui se cassent la figure dès la première erreur silencieuse en production.

### ICP cible

| Critère | Valeur |
|---------|--------|
| Type d'entreprise | Sous-traitant mécanique de précision |
| Taille | 10-50 personnes |
| Parc machines | 5-25 machines CN |
| Secteur de débouchés | Aéro / auto / médical / défense Tier 2 ou 3 |
| Géographie France | Auvergne-Rhône-Alpes, Bourgogne, Pays de la Loire, Grand Est |
| Géographie Maghreb | Casablanca, Tanger Med, Tunis-Sfax, Bordj Bou Arreridj |

**Volume cible :** 2 500-3 500 entreprises France + 800-1 500 Maghreb.

---

## 2. Architecture technique (vue fonctionnelle)

### 2.1 Le principe directeur

Le LLM ne génère **jamais** de code OR-Tools direct. Cette règle est non-négociable.

Toute la machinerie de modélisation passe par une bibliothèque interne de patterns CP-SAT testés et garantis, exposée au LLM sous forme d'outils MCP de haut niveau sémantique métier.

**Le LLM est cantonné à des rôles précis :**

- Extraction structurée d'informations depuis le langage naturel ou les documents clients
- Data cleaning et fuzzy matching sur les données importées
- Traduction des préférences métier exprimées en langage naturel vers la couche soft constraints
- Explication des résultats et des situations complexes en langage naturel
- Modifications conversationnelles légères en cours d'usage

**Tout le reste** — choix des patterns durs, génération du modèle CP-SAT, exécution du solveur, validation, calcul des KPI — est du code Python déterministe.

### 2.2 Les agents LLM : 2, pas 3

L'architecture multi-agents se simplifie en deux agents seulement :

**Agent d'extraction et préparation**
- Prend les inputs utilisateur : questionnaire arborescent, fichiers Excel/CSV, modifications conversationnelles, demandes de replanification
- Produit une spécification structurée (data structures validées)
- Gère le data cleaning
- Traduit les préférences exprimées en langage naturel vers la couche de soft constraints
- **Ne génère pas de code**

**Agent d'explication et validation**
- Analyse les résultats produits par le solveur
- Traduit en langage naturel pour le chef d'atelier
- Détecte les incohérences
- Génère les explications de placement d'OF
- Gère la communication des cas d'incertitude et des INFEASIBLE

Entre ces deux agents, le pipeline est entièrement déterministe : application des templates, exécution CP-SAT, validation par cas-tests internes, simulation opérationnelle.

### 2.3 Les trois catégories de contraintes

C'est l'architecture la plus structurante du produit.

#### Contraintes dures
Ce qui ne peut absolument pas être violé. Modélisées par des patterns CP-SAT fermés et testés :
- `no_overlap_with_setup`
- `qualified_operator_constraint`
- `calendar_availability`
- `precedence_chain`
- `shared_resource_exclusion`
- `sequence_dependent_transition`

Le LLM ne les écrit pas, il les active avec des paramètres validés. Si un client a besoin d'une contrainte dure non couverte, c'est un dev produit, pas une feature de l'agent.

#### Contraintes calendaires et données métier
Disponibilités, qualifications, calendriers, gammes opératoires, OF en cours. Saisies via le questionnaire arborescent ou les imports, stockées dans le modèle de données structuré.

#### Soft constraints et préférences (nouveauté V3)
Cette couche capture les règles que les chefs d'atelier expriment en langage naturel et qui ne rentrent dans aucun pattern formel :

- *"On préfère éviter de faire tourner la machine X la nuit"*
- *"Cet opérateur peut dépanner mais on évite"*
- *"Regrouper si possible les pièces de la même matière"*

Le LLM traduit ces phrases en pondérations qui rentrent dans la fonction objectif sous forme de pénalités, sans toucher à la modélisation dure. Techniquement faisable proprement avec CP-SAT via variables booléennes optionnelles et pénalités dans l'objectif.

C'est cette couche qui résout le problème de rigidité des patterns fermés tout en gardant la sécurité du système.

### 2.4 Les outils MCP exposés

#### Outils de modélisation
```
create_workshop_model(workshop_name, description)
add_machine(model_id, name, type, calendar, shared_resources)
add_operator(model_id, name, qualifications, availability)
add_orders_from_excel(model_id, file_path)
apply_pattern(model_id, pattern_name, parameters)
add_soft_constraint(model_id, natural_language_rule, weight_hint)
```

#### Outils de versioning (critiques pour le support)
```
get_model_snapshot(model_id)
diff_models(model_id_v1, model_id_v2)
rollback_model(model_id, version)
```

#### Outils d'exécution et explication
```
solve_schedule(model_id, horizon, objective_weights, freeze_horizon)
get_solution(job_id)
explain_decision(job_id, operation_id)
analyze_infeasibility(model_id, mis_result)
validate_against_test_cases(model_id)
run_operational_simulation(job_id)
```

L'agent ne pilote jamais directement le solveur. Il appelle des opérations métier qui maîtrisent ta bibliothèque interne de patterns CP-SAT.

### 2.5 Choix techniques structurants

**OR-Tools CP-SAT en direct, pas MiniZinc**
- Performance brute meilleure
- API Python s'intègre proprement dans un SaaS production
- Contrôle fin (search strategy, hints, callbacks) essentiel
- La modélisation idiosyncratique de CP-SAT est isolée du LLM par tes templates

**Pas de réimplémentation de Large Neighborhood Search**
- CP-SAT a un LNS natif performant
- Tu structures ton problème pour qu'il en bénéficie correctement

**Stack production**
- NestJS pour l'API et la gestion utilisateurs
- Microservice Python isolé pour OR-Tools et les agents LLM
- Communication via queue asynchrone (BullMQ + Redis)
- PostgreSQL multi-tenant
- Stripe pour la facturation
- Déploiement initial Hetzner ou Scaleway, migration cloud hyperscaler en année 2-3 si besoin

---

## 3. Le module Data Quality

### Pourquoi c'est critique

Les données d'entrée d'une PME méca sont notoirement sales. Tu vas trouver dans les Excel clients :

- Références matières écrites de 5-10 façons différentes (`"Alu 7075"`, `"AL-7075"`, `"7075 T6"`, `"ALU 7075-T6"`)
- Nomenclatures incomplètes avec opérations omises
- Temps de cycle estimés il y a 4 ans
- Références client orthographiées différemment (`"Safran"`, `"SAFRAN"`, `"Safran Aircraft"`)
- Unités mélangées (minutes/heures, mm/centièmes)
- Dates dans plusieurs formats dans le même fichier

Sans couche dédiée, le solveur produit un planning parfait d'une réalité fausse. **C'est probablement 30-40% du travail de développement de l'agent d'extraction.**

### Composants du module

#### Détection automatique du format
Chaque ERP exporte différemment. Le système doit reconnaître les patterns Sage / Cegid / Clipper / Excel libre et adapter le mapping.

#### Normalisation des références (fuzzy matching)
- Algorithme : Levenshtein normalisé + dictionnaire métier + apprentissage progressif via les corrections client
- Couvre matières, clients, opérations

#### Détection des aberrations
- Temps de réglage à zéro sur opération CN
- Durées négatives
- Références matière inexistantes
- Valeurs aberrantes statistiquement (au-delà de 3 sigmas par rapport à l'historique)

#### Réconciliation avec l'historique
Si `"AL-7075"` a déjà été normalisé en `"Aluminium 7075-T6"` la fois précédente, le système le mémorise et propose la même normalisation. Apprentissage par client.

#### Dashboard qualité
L'utilisateur voit *"127 OF importés, 122 propres, 5 nécessitent validation"*, avec pour chaque ligne problématique la valeur surlignée et un champ de correction direct.

### Logique de gestion des aberrations en 3 niveaux

Le système ne rejette pas silencieusement des données client (inacceptable en industriel) ni n'accepte aveuglément n'importe quoi (voie royale aux plannings absurdes).

#### Niveau 1 — anomalies certaines
- **Action :** import bloqué pour ces lignes spécifiquement, le reste passe
- **Cas typiques :** temps de réglage = 0 sur opération CN, durée d'OF négative, référence matière inexistante
- **UX :** dashboard d'erreurs ciblées, pas de blocage global

#### Niveau 2 — anomalies probables
- **Action :** import accepté avec flag "à confirmer", suggestion contextuelle
- **Exemple :** *"le temps de réglage de 5 min pour cette opération CN est inhabituel — votre historique sur 12 mois indique 25-45 min en moyenne pour ce type de pièce. Voulez-vous corriger ou confirmer ?"*
- **Conséquence :** l'OF rentre dans le solveur, mais le score de confiance global du planning est dégradé proportionnellement au nombre d'anomalies non-confirmées

#### Niveau 3 — valeurs surprenantes mais possibles
- **Action :** import accepté silencieusement
- **Conséquence :** événement tracé dans le journal d'apprentissage pour enrichir progressivement les seuils de détection

---

## 4. Le questionnaire arborescent conditionnel

### Pourquoi arborescent et non linéaire

**Risque du chat ouvert :** le LLM ne devine pas les contraintes physiques que le client n'a pas verbalisées (*"la machine Y et la machine X partagent le même réseau d'aspiration, elles ne peuvent pas tourner simultanément"*). Aucun chef d'atelier ne te dira ça spontanément — c'est un truisme physique de son atelier.

**Risque du questionnaire linéaire de 50 questions :** fatigue cognitive, abandon en cours de route, réponses approximatives, faux sentiment de complétude.

**L'arbre conditionnel résout les deux :** la première question filtre le segment, et selon la réponse l'arbre se déploie différemment. Si le client n'a pas de traitement thermique interne, on ne pose pas les 4 questions associées. Si le client n'a qu'une seule équipe, on ne pose pas les questions sur les rotations 3x8.

### Structure cible

- **Total dans l'arbre :** 80-150 questions
- **Vues par client :** 15-25 questions selon profil
- **Profondeur :** variable selon complexité détectée

### Catégories couvertes

| Catégorie | Exemples de questions |
|-----------|----------------------|
| Profil d'activité | Tournage, fraisage, rectification, multi-axes |
| Partages de ressources | Aspiration, alimentation, fluides, espace |
| Incompatibilités de proximité | Vibrations, contamination |
| Structure opérateurs | Équipes, qualifications, polyvalence, rotations |
| Calendrier détaillé | Pauses, changements d'équipe, maintenance préventive |
| Sous-traitances externes | Traitement thermique, revêtement, contrôle |
| Exigences qualité | EN 9100, IATF 16949, ISO 13485 |
| Spécificités matières | Matières et outillage |

### Onboarding progressif

Pas tout en upfront.

1. **15 questions essentielles au démarrage** — les vrais bloquants physiques qui peuvent rendre tous les plannings absurdes si non capturés
2. **Mini-questionnaires contextuels** déclenchés par l'usage — la première fois que le système rencontre tel pattern de configuration, il pose 2-3 questions ciblées
3. **Étalement** sur les 4-6 premières semaines d'usage

Le questionnaire devient un actif propriétaire qui s'enrichit avec chaque nouveau client — tu sais poser les bonnes questions là où tes concurrents demandent *"décrivez votre atelier"*.

---

## 5. Périmètre V1 — discipline du wedge

### Ce que la V1 fait

Sept fonctionnalités, et rien d'autre :

1. **Questionnaire d'onboarding arborescent** avec progression sur 4-6 semaines
2. **Module Data Quality** avec import Excel/CSV, fuzzy matching, dashboard qualité, logique 3 niveaux
3. **Moteur d'ordonnancement** avec patterns durs CP-SAT, soft constraints traduites depuis le langage naturel, fonction objectif composite calibrée dynamiquement, résolution < 60 secondes pour 80% des cas
4. **PWA tactile pour les opérateurs** : scan QR codes des OF, déclarations début/fin d'opération, signalement de problèmes par photo, offline-first
5. **Tableau de bord chef d'atelier** : Gantt interactif, KPI temps réel, alertes prédictives, modification conversationnelle ("mets l'OF Safran en priorité 1...")
6. **Module d'analyse d'infaisabilité** : INFEASIBLE → explications métier + 2-3 actions correctives concrètes
7. **Versioning du modèle** avec snapshot, diff, rollback exposés au client via UX d'historique

### Ce que la V1 ne fait PAS

| Hors périmètre | Raison |
|----------------|--------|
| Connecteur ERP automatisé (Sage X3, Cegid, Clipper) | Phase 2 |
| Application mobile native | PWA suffit |
| Multi-langue | Tout en français au démarrage |
| Connecteur machine CN (MTConnect / OPC-UA) | 6 mois de dev, valeur marginale tant que la saisie tablette fonctionne |
| SSO, SAML, SOC 2 | ICP PME ne le demande pas |
| API publique riche | Juste l'API privée pour le frontend |
| Personnalisation profonde par client | Si 3 prospects demandent la même customisation, on en fait une feature |

---

## 6. Le trust layer — le chantier principal du produit

### Le problème central

Le risque principal n'est pas la performance technique mais la fiabilité opérationnelle perçue.

> Une seule erreur de planning silencieuse chez un client te coûte 15-30K€ de churn et de réputation locale.
> À 50 clients, une erreur silencieuse par mois et par client te tue le business en 18 mois.

**Le taux de réussite réaliste en production est de 80-90%** sur des cas industriels combinés, pas 95%. Cette différence de 5-15 points distingue les démos contrôlées de la production réelle.

### Les 5 mécanismes du trust layer

#### 1. Détection automatique d'incertitude
Avant toute remontée de planning au client, le système calcule un score de confiance basé sur des heuristiques internes :
- Nombre de patterns combinés inhabituels
- Nombre de cas-tests passés vs partiellement passés
- Écart entre la meilleure solution trouvée et la seconde
- Complexité combinatoire du problème
- Nombre d'anomalies Data Quality non-confirmées

Si le score est bas, le système ne livre pas le planning automatiquement.

#### 2. Validation par cas-tests internes
Bibliothèque de 100-200 mini-scénarios industriels dont la solution optimale ou la faisabilité est connue.

Après chaque génération de modèle, ces cas-tests sont rejoués automatiquement. Si le modèle échoue sur un cas-test critique, retour en boucle pour correction. **Le solveur ne tourne sur le vrai problème client qu'après validation.**

#### 3. Simulation opérationnelle post-solveur
C'est le mécanisme qui distingue la cohérence mathématique de l'utilisabilité opérationnelle.

Un planning peut être mathématiquement optimal et opérationnellement absurde :
- Alterner les setups toutes les 30 minutes au lieu de regrouper
- Créer des micro-pauses irréalistes de 12 minutes entre deux opérations
- Fragmenter excessivement une série

CP-SAT ne sait pas que ça crée un chaos atelier.

**Métriques humaines mesurées :**
- Fragmentation des séries (nombre moyen d'OF d'une même famille séparés)
- Nombre de transitions par opérateur par poste
- Présence de micro-pauses inférieures à 15 minutes
- Amplitude de re-déploiement des opérateurs entre machines
- Ratio temps utile / temps de réglage

Si ces métriques dépassent des seuils calibrés, le planning est rejeté ou recyclé avec contraintes supplémentaires injectées dans la fonction objectif.

#### 4. Circuit breaker déterministe
En cas d'INFEASIBLE répété ou d'échec de validation, le système ne boucle pas indéfiniment sur le LLM.

**Après 3 tentatives :** basculement automatique sur l'analyse formelle.
- Extraction du Minimum Infeasible Subset (MIS) via l'API CP-SAT native
- Traduction en langage naturel par le LLM cantonné à ce rôle
- Présentation au chef d'atelier avec 2-3 actions correctives

L'humain reprend la main avec une compréhension claire du blocage.

#### 5. Le chef d'atelier garde toujours le dernier mot
**Pas d'auto-pilote.** Le système propose, le chef d'atelier valide ou modifie.

Cette boucle de validation humaine est non négociable, même pour des plannings où le système est très confiant. Pour deux raisons :
- Sécurité ultime contre les erreurs silencieuses
- Le chef d'atelier perçoit le produit comme un copilote, pas un remplaçant

---

## 7. Modélisation des points sensibles

### 7.1 Sequence-dependent setup time avec clustering automatique

**Modélisation canonique gravée dans le marbre :**
- `AddNoOverlap` avec transition matrix dans CP-SAT
- Pas d'arcs ni de circuit (s'écroulent en performance sur de gros volumes)
- Pas d'intervalles optionnels complexes
- Une seule façon de faire, codée dans un template fermé, testée exhaustivement

Le LLM ne touche jamais à cette modélisation. Il fournit uniquement les groupes de familles de pièces et la matrice de temps de transition.

#### Le problème de la taille de matrice
Pour un atelier de 100 pièces différentes : matrice 100×100 = 10 000 cellules. **Aucun chef d'atelier ne va remplir ça à la main.**

#### Solution : clustering automatique des familles
- Détection automatique des groupes de pièces similaires (matière, forme, outillage requis, temps de cycle)
- Algorithme : clustering hiérarchique sur features extraites des nomenclatures
- Résultat : 5-15 familles au lieu de 100 pièces individuelles
- Matrice : 15×15 = 225 cellules — gérable

**UX :** *"voici les 8 familles détectées avec exemples de pièces, ajustez si besoin"*. Le client valide, puis remplit ou laisse le système estimer les temps de transition entre familles à partir de l'historique.

### 7.2 Replanification incrémentale avec stabilité par criticité

**Trois mécanismes combinés :**

1. **Freeze partiel** des opérations en cours et de l'horizon court (4-8 heures), qui deviennent des constantes dans le solveur
2. **Solution hint** CP-SAT injectant la solution précédente, pour démarrage rapide
3. **Fonction objectif composite calibrée dynamiquement**

**Formulation de la stabilité :**

Le terme de stabilité n'est pas naïvement le nombre de tâches déplacées.

> Déplacer 3 OF Safran prioritaires = chaos perçu.
> Déplacer 20 OF non-critiques = passe tranquillement.

Formulation correcte :
```
Stabilité = Σ (Tâche_déplacée × Criticité_OF × Décalage_temporel)
```

Avec criticité issue d'une hiérarchie métier :
- Tier 1 stratégique : poids > 10
- Tier 2 important : poids 5
- Tier 3 standard : poids 1

Le LNS natif de CP-SAT optimise ensuite cette fonction sans réimplémentation custom.

### 7.3 Calibration dynamique des poids dans la fonction objectif

**Le problème :** sans calibration, l'objectif composite a un problème d'ordre de grandeur.
- Makespan : valeur typique 5000 (minutes)
- Retards : valeur typique 3-5 (jours pondérés)
- Stabilité : valeur typique 50-150 (points pondérés)

Sans normalisation, la pénalité Makespan écrase tout le reste, ou la pénalité Tardiness devient invisible. Le LNS converge vers des optima locaux médiocres.

**Solution :** module de calibration dynamique qui, avant chaque solving :
1. Estime les ordres de grandeur des trois composantes sur l'instance courante (pré-résolution rapide ou heuristiques)
2. Normalise les poids en conséquence
3. Le client définit des **priorités relatives** ("retards vs stabilité = 70/30")
4. Le système calcule les poids absolus normalisés

Invisible côté client, mais c'est ce qui fait la différence entre un solveur qui converge proprement et un solveur médiocre.

### 7.4 Traduction INFEASIBLE → langage naturel

Quand le solveur retourne INFEASIBLE, l'outil `analyze_infeasibility` enchaîne deux étapes :

**Étape 1 : calcul déterministe du MIS** via l'API CP-SAT — le plus petit ensemble de contraintes qui rend le problème impossible.

**Étape 2 : traduction en langage métier** par le LLM cantonné à ce rôle.

**Exemple de sortie :**
> *"Le planning est impossible parce que vous demandez à la rectifieuse Studer de traiter 12 heures d'OF entre lundi et mardi alors qu'elle n'est disponible que 8 heures sur cette période."*

**Actions correctives proposées (2-3) :**
- Reporter l'OF X
- Sous-traiter Y
- Étendre l'horizon de Z

C'est probablement la fonction la plus précieuse pour le chef d'atelier au quotidien.

---

## 8. Business model et coûts

### 8.1 Pricing

#### Installation et calibration en atelier (non négociable)

| Taille atelier | Prix |
|----------------|------|
| ≤10 machines | 5 000€ |
| 10-30 machines | 12 000€ |

**Inclus :**
- Présence terrain (1-2 jours)
- Transfert de connaissance avec l'équipe client
- Vérification physique des contraintes implicites
- Validation des premiers plannings avec le chef d'atelier
- 30 jours de support intensif

> Ce n'est pas du temps facturé pour configurer un logiciel — c'est du temps facturé pour **transférer la responsabilité de la pertinence métier** de toi à l'équipe client.

#### Abonnement mensuel

| Utilisateurs | Prix /mois |
|--------------|------------|
| ≤10 | 800€ |
| 11-25 | 1 500€ |
| 26-50 | 2 500€ |

#### Modules optionnels (année 2)
- Connecteurs ERP avancés : +200-400€/mois
- Copilote méthodes IA : +300€/mois
- Connecteurs IoT machines : +400-600€/mois

### 8.2 Coûts d'inférence LLM

| Phase | Coût |
|-------|------|
| Onboarding | 2-5€ par client |
| Usage mensuel en croisière | 10-40€ par client |

Sur un ARPU de 1 500€/mois, c'est moins de 3% du revenu.

| Volume clients | Coût LLM mensuel |
|----------------|------------------|
| 60 clients | ~1 500€ |
| 500 clients | ~15 000€ |

**Le vrai coût caché à éviter :** les erreurs de planning silencieuses qui coûtent 15-30K€ de churn par incident. Donc ne sois jamais radin sur les tokens consacrés à la validation, simulation opérationnelle et double-vérification.

### 8.3 Stratégie de fallback LLM

| Provider | Rôle | Coût de portabilité |
|----------|------|---------------------|
| Claude Sonnet | Primaire — excellence en suivi d'instructions et MCP | — |
| Mistral Large | Fallback souverain européen | Faible si prompts standardisés |
| DeepSeek-R1 local | Cas air-gapped uniquement | Élevé (GPU H100/A100 nécessaires) |

**Architecture défensive :** abstraction MCP qui te rend largement indépendant du fournisseur, avec tests de non-régression multi-modèles automatisés.

---

## 9. Trajectoire et go-to-market

### 9.1 Phasage en 4 étapes

#### Phase 0 (mois 0-3) — Validation par découverte client
- 15-20 entretiens avec des chefs d'atelier de sous-traitance méca
- Construction du questionnaire arborescent en parallèle
- Pas une ligne de code de produit avant la fin de cette phase
- Construction de la bibliothèque initiale de patterns CP-SAT par modélisation manuelle de 5-10 cas réels

#### Phase 1 (mois 3-9) — MVP avec design partners équilibrés
- Construction du produit V1
- Déploiement chez 5-7 sous-traitants méca pilotes (500€/mois pendant 3 mois, puis tarif standard)

**Composition critique des design partners :**
- ≥2 français certifiés EN 9100 ou équivalent aéro Tier 2 (pour éviter l'overfitting culturel)
- 2-3 français généralistes
- 1-2 maghrébins certifiés

**Critères de sortie :**
- 4-5/7 utilisent le produit ≥3 fois par semaine après 60 jours
- 3/7 acceptent le passage au tarif standard

#### Phase 2 (mois 9-18) — Premier scale
- 30 clients payants en France, 10-15 au Maghreb
- Premier intégrateur partenaire actif (Apsi, Absys Cyborg, Astride ou Visiativ)
- Construction des 2 premiers connecteurs ERP (probablement Sage X3 et Clipper)

**Critères :**
- CAC < 12K€
- Churn brut < 15%
- NPS chef d'atelier > 30

#### Phase 3 (mois 18-36) — Densification
- 100-150 clients
- Ouverture deuxième sous-vertical (chaudronnerie/métallerie)
- Maghreb consolidé
- Levée Series A si besoin (8-15M€) ou poursuite en bootstrap

**Critères :**
- 1,5-2,5M€ ARR
- Marge brute > 70%

### 9.2 La séquence géographique avec garde-fou anti-overfitting

**Stratégie :** Maghreb-first sur le démarrage produit pour le cash-flow et la rapidité d'apprentissage. Mais France-active dès la phase 1 avec design partners certifiés aéro pour garantir que ta modélisation métier encaisse la complexité de l'ICP final.

**Le risque à éviter :** construire un produit qui fonctionne parfaitement pour des sous-traitants Tier 3 maghrébins (volume, simplicité) et qui échoue ensuite à l'audit qualité des donneurs d'ordre français aéro Tier 2 (EN 9100, AS9100, IATF 16949, ISO 13485).

**Garde-fou :** les 2 design partners français certifiés en phase 1 sont **obligatoires, pas optionnels**.

Au Maghreb, privilégier les sous-traitants aéro certifiés (zones de Casablanca, Tanger Med, Tunis-Sfax) plutôt que les généralistes — eux aussi sont soumis aux mêmes normes puisqu'ils livrent les mêmes donneurs d'ordre Airbus/Safran.

---

## 10. Stratégie de défensibilité 3-5 ans

> L'IA et le MCP en eux-mêmes ne sont pas un moat.
> Dans 24-36 mois, JITbase, Mercateam, Sage et Cegid auront tous une chatbox LLM.

Ce qui te défend vraiment, c'est la combinaison de **5 actifs accumulés** que les concurrents ne peuvent pas répliquer rapidement :

### 1. Le corpus de patterns industriels validés
Bibliothèque CP-SAT testée sur 100+ ateliers réels devient un actif de plus en plus dur à reproduire avec le temps. Chaque nouveau cas client enrichit la couverture.

Les concurrents legacy qui essaient d'ajouter une couche LLM sur leurs vieux systèmes rigides échoueront sur la fiabilité — c'est un avantage structurel.

### 2. Les intégrations ERP profondes
Une fois Sage X3 ou Clipper proprement extraits chez un client (nomenclatures, gammes opératoires, données historiques), le coût de switch devient prohibitif. Cette stickiness se construit en année 1-2.

### 3. Le dataset de modélisations vérifiées
Corpus anonymisé de cas réels qui te permet d'affiner progressivement :
- L'extraction des contraintes métier implicites
- Le clustering des familles
- La normalisation des références

> Aucun benchmark académique ne vaut un dataset de 500 ateliers réels.

### 4. Les références terrain
Une fois que tu équipes 10-20 sous-traitants Tier 2 d'Airbus ou Stellantis, tu deviens "le standard" du segment. Les nouveaux entrants doivent te déloger référence par référence — extrêmement long et coûteux.

### 5. L'UX décisionnelle accumulée (nouveauté V3)
Comment le chef d'atelier comprend une situation, prend une décision, et agit, en combien de temps.

Cette expérience décisionnelle se raffine avec chaque session client, chaque retour terrain, chaque amélioration de l'agent d'explication. Au bout de 24 mois, ton produit "se pilote" avec un naturel que les concurrents ne peuvent pas atteindre rapidement.

> Les concurrents peuvent copier ton LLM, ton CP-SAT, ton MCP.
> Ils ne peuvent pas copier l'expérience décisionnelle accumulée par tes clients dans ton produit.

### Ton obsession au quotidien

Pas la techno IA. Mais :
1. L'enrichissement de la bibliothèque MCP de patterns spécifiques à la mécanique de précision
2. La qualité du trust layer
3. Le raffinement continu de l'UX décisionnelle

---

## 11. Critères go/no-go à chaque étape

### Fin de phase 0 (mois 3)

| Critère | Si non rempli |
|---------|---------------|
| Wedge précis identifié | Pivot |
| 5-7 design partners engagés moralement | Pivot |
| ≥2 design partners français certifiés aéro avec accès aux données | Pivot |

### Fin de phase 1 (mois 9)

| Critère | Si non rempli |
|---------|---------------|
| 4-5/7 design partners utilisent régulièrement à 60 jours | Repenser le trust layer avant tout scale |
| Erreurs silencieuses < 1 par client par mois | Repenser le trust layer avant tout scale |

> Le scale d'un produit avec un trust layer cassé est un suicide en mouvement.

### Fin de phase 2 (mois 18)

| Critère | Si non rempli |
|---------|---------------|
| CAC < 15K€ | Réécrire le pitch, couper des fonctionnalités |
| Churn < 20% | Réécrire le pitch, couper des fonctionnalités |

### Le signal qualitatif du PMF

> Un chef d'atelier qui te dit spontanément *"je peux plus revenir à Excel après ça"*.

Si tu ne l'entends pas après 12 mois et 30 clients, c'est que le wedge n'était pas le bon.

---

## 12. Ce qui change par rapport à la V2

### 1. La couche soft constraints devient une catégorie architecturale à part entière
Trois catégories de contraintes (dures / calendaires-données / soft) au lieu de deux. Cette troisième couche résout le problème de rigidité des patterns fermés.

### 2. Le module Data Quality devient un composant majeur de l'agent d'extraction
Avec fuzzy matching, normalisation, dashboard qualité, et la logique en 3 niveaux pour les aberrations. Probablement 30-40% du travail de la V1.

### 3. Le questionnaire passe de linéaire à arborescent conditionnel
80-150 questions dans l'arbre, chaque client n'en voit que 15-25. Onboarding progressif avec 15 questions essentielles upfront et mini-questionnaires contextuels sur 4-6 semaines.

### 4. Le trust layer passe de 4 à 5 mécanismes
Ajout de la simulation opérationnelle post-solveur qui mesure les métriques humaines (fragmentation, transitions, micro-pauses, amplitude de re-déploiement).

### 5. Trois nouveaux outils MCP de versioning
`get_model_snapshot`, `diff_models`, `rollback_model` deviennent obligatoires en V1.

### 6. Deux raffinements techniques majeurs
- Clustering automatique des familles de pièces (matrice 15×15 au lieu de 100×100)
- Calibration dynamique des poids dans la fonction objectif composite
- Pondération de la stabilité par criticité métier (Tier 1/2/3) plutôt que simple comptage

### 7. L'UX décisionnelle devient le 5ème actif défensif
Pas un moat à elle seule mais un moat composite avec les 4 autres.

### 8. Le repositionnement du setup en "installation et calibration en atelier"
Résout la contradiction perçue entre "onboarding automatisé" et "setup payant 5-12K€". Et la stratégie ICP intègre désormais l'obligation d'au moins 2 design partners français certifiés aéro dès la phase 1.

---

*Fin du document — V3*
