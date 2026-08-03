# Task 1 Construction Update Candidates

## Data Contract

- This document contains synthetic data for a fictional university created for research. It does not correspond to any actual university,
  building, construction project, or operational notice.
- There are exactly 75 candidates, and the counts for the six categories are, in order,
  `11 / 10 / 15 / 13 / 17 / 9`.
- Only the `Content` of each item is a Memory candidate. The identifier, Memory Location,
  Audience, Baseline Relationship, and Review Status are supplementary annotations for design and validation
  and must not be included in the Memory content.
- `Memory Location` is a stable hierarchical locator sidecar. The first segment is
  `construction-updates`, the second is one of the six subordinate Contexts, and the final leaf
  preserves the original order and atomic-splitting semantics.
- The `Baseline Relationship` within each item is a descriptive annotation preserving the initial authoring context.
  Use `task-1-update-actions-en.tsv` to determine which Memory in which subordinate Context
  is actually modified or where a new Memory is added. Candidates that retain an existing fact
  unchanged or add a duplicate are not included in this update set.
- `Audience` expresses only the intended future visibility. It does not imply
  role-based access control in the current prototype.
- All place names are fictional and generic. No actual school names, city names, addresses,
  personal names, or operator names are used.

## Building Access · 11

### T1-U-001

- Memory Location: construction-updates/building-access/01
- Content: During the construction period, the third-floor rear entrance cannot be used for general passage.
- Audience: All
- Baseline Relationship: Modifies the existing content stating that both entrances are open and also modifies the route connecting to the Central Library.

### T1-U-003

- Memory Location: construction-updates/building-access/03-hours
- Content: During the construction period, the end time for general access through the main entrance is shortened from 10:00 p.m. to 5:00 p.m.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable hours content from the original compound candidate T1-U-003.

### T1-U-068

- Memory Location: construction-updates/building-access/03-ramp
- Content: During the construction period, the existing accessible route cannot be used because it is being reconstructed.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable ramp content from the original compound candidate T1-U-003.

### T1-U-069

- Memory Location: construction-updates/building-access/03-temp-route
- Content: The temporary accessible route next to the main entrance can be used throughout the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable temp-route content from the original compound candidate T1-U-003.

### T1-U-004

- Memory Location: construction-updates/building-access/04
- Content: Instruct students authorized to enter after 5:00 p.m. to use a physical NFC student ID card rather than the app.
- Audience: Students; Staff
- Baseline Relationship: Modifies the existing content stating that either a physical card or the app can be used.

### T1-U-006

- Memory Location: construction-updates/building-access/06-staff-entrance
- Content: During the construction period, instruct staff and construction/facilities personnel to use only the designated staff entrance instead of the third-floor rear entrance.
- Audience: Staff; Construction/Facilities Personnel
- Baseline Relationship: Modifies the staff-only entrance to restrict its users to groups authorized during the construction period and to make it replace the third-floor rear entrance.

### T1-U-048

- Memory Location: construction-updates/building-access/08-explain-access
- Content: In access guidance during the construction period, the access guidance agent may prioritize the 5:00 p.m. closing of the main entrance and the closure of the third-floor rear entrance.
- Audience: All
- Baseline Relationship: Modifies the existing Self Model that explained normal opening hours to prioritize information for the construction period.

### T1-U-049

- Memory Location: construction-updates/building-access/09
- Content: A student accustomed to reaching the Central Library through the third-floor rear entrance may expect to be able to pass through during the construction period, go as far as the closed rear entrance, and then turn back or search again for an alternative route there.
- Audience: All
- Baseline Relationship: Modifies the normal habit of using the rear entrance into an expectation that passage will remain possible during the construction period and into renewed route-search behavior at the closure point.

### T1-U-050

- Memory Location: construction-updates/building-access/10
- Content: During the construction period, the general accessible route bypasses the existing accessible route under reconstruction and leads from the temporary passage next to the main entrance to the first-floor lobby.
- Audience: All
- Baseline Relationship: Adds a new Memory for the spatial relationship connecting the closure of the existing accessible route and the availability of the temporary passage.

### T1-U-061

- Memory Location: construction-updates/building-access/11-proactive-warning
- Content: Proactively inform students who are trying to reach the Central Library or who normally use the third-floor rear entrance that they cannot use that route during the construction period.
- Audience: Students
- Baseline Relationship: Adds a new Memory for a policy of providing proactive guidance before users reach the closed route, based on confirmed usage habits.

### T1-U-062

- Memory Location: construction-updates/building-access/om-tour-leader-route-expectation
- Content: A leader of an external group tour may expect the route used on a previous visit to remain valid during the construction period and lead the visiting group to the closed third-floor rear entrance.
- Audience: All
- Baseline Relationship: Modifies an external group tour leader's preference for a previous-visit route into an expectation of using the same rear entrance during the construction period and the possibility of an incorrect approach.

## Event Relocations · 10

### T1-U-008

- Memory Location: construction-updates/event-relocations/01-viewing
- Content: Viewing in the tenth-floor exhibition and event hall is suspended during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable viewing content from the original compound candidate T1-U-008.

### T1-U-009

- Memory Location: construction-updates/event-relocations/02-reservations
- Content: Do not accept new reservations for Main Building event venues during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable reservations content from the original compound candidate T1-U-009.

### T1-U-076

- Memory Location: construction-updates/event-relocations/02-east-auditorium
- Content: During the construction period, direct users to the auditorium in the detached east building as an alternative to Main Building event venues.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable east-auditorium content from the original compound candidate T1-U-009.

### T1-U-077

- Memory Location: construction-updates/event-relocations/02-engineering-room
- Content: During the construction period, direct users to the third-floor multipurpose room in the Engineering Building as an alternative to Main Building event venues.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable engineering-room content from the original compound candidate T1-U-009.

### T1-U-010

- Memory Location: construction-updates/event-relocations/03
- Content: During the construction period, the auditorium in the detached east building is converted into an alternative event space for Main Building events.
- Audience: All
- Baseline Relationship: Adds the new role of alternative space created by the relocation of Main Building events without repeating the existing fact that the building operates independently.

### T1-U-051

- Memory Location: construction-updates/event-relocations/04-compare-venues
- Content: During the construction period, the event guidance agent may exclude closed Main Building event venues from comparison candidates and compare only designated alternative spaces.
- Audience: All
- Baseline Relationship: Modifies the existing Self Model that compared posted spaces to exclude closed spaces.

### T1-U-078

- Memory Location: construction-updates/event-relocations/04-no-booking
- Content: During the construction period, the event guidance agent cannot create or restore reservations for Main Building event venues and may provide only the reservation channel for each alternative space.
- Audience: All
- Baseline Relationship: Modifies the reservation routes to provide during the construction period without repeating the general limitation on creating reservations.

### T1-U-052

- Memory Location: construction-updates/event-relocations/05-location-questions
- Content: An external visitor who has previously visited a Main Building event venue may expect the entrance and floor from the previous visit to remain unchanged and miss guidance about the alternative venue during the construction period.
- Audience: All
- Baseline Relationship: Modifies a returning visitor's existing habit of using the same entrance and floor into an expectation that the location will remain the same and the possibility of missing guidance about the alternative venue.

### T1-U-053

- Memory Location: construction-updates/event-relocations/06
- Content: During the construction period, the separate loading entrance of the auditorium in the detached east building is converted into the loading point for event equipment relocated from the Main Building.
- Audience: All
- Baseline Relationship: Adds the loading relationship changed by the event relocation without repeating the existing fact that the facilities are separate.

### T1-U-063

- Memory Location: construction-updates/event-relocations/om-event-operators
- Content: An external event operator may assume that the existing Main Building loading procedure remains valid during the construction period, send equipment to the existing loading entrance, or check the access rules for the alternative venue too late.
- Audience: All
- Baseline Relationship: Modifies the normal tendency to check loading information into an expectation that the existing procedure will remain in place and the possibility of choosing the wrong loading entrance.

## Temporary Parking · 15

### T1-U-011

- Memory Location: construction-updates/temporary-parking/01
- Content: During the construction period, the underground parking garage cannot be used for general parking.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable general-parking content from the original compound candidate T1-U-011.

### T1-U-012

- Memory Location: construction-updates/temporary-parking/02-locked-door
- Content: During the construction period, the pedestrian entrance door to the underground parking garage is kept locked.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable locked-door content from the original compound candidate T1-U-012.

### T1-U-013

- Memory Location: construction-updates/temporary-parking/03
- Content: During the construction period, instruct staff to use a physical access card to pass through the locked pedestrian entrance door to the underground parking garage.
- Audience: Staff
- Baseline Relationship: Adds credential-based access not present in the existing content.

### T1-U-014

- Memory Location: construction-updates/temporary-parking/04
- Content: Instruct construction/facilities personnel to access the underground parking garage through the controlled on-site access procedure that has been approved.
- Audience: Construction/Facilities Personnel
- Baseline Relationship: Adds an access exception for construction personnel not present in the existing content, while keeping the exact approved hours and control points only in query-only materials.

### T1-U-015

- Memory Location: construction-updates/temporary-parking/05
- Content: The stairs from the Main Building down to the underground parking garage are closed to all users.
- Audience: All
- Baseline Relationship: Modifies the existing content stating that the stairs can be used.

### T1-U-016

- Memory Location: construction-updates/temporary-parking/06
- Content: The underground parking garage is used as a temporary storage area for construction materials.
- Audience: Staff; Construction/Facilities Personnel
- Baseline Relationship: Adds an operational status not present in the existing content. The types, quantities, and arrangement of materials are separated into query-only materials.

### T1-U-082

- Memory Location: construction-updates/temporary-parking/07-lost-property
- Content: After the clear-out, personal items left in the underground parking garage were moved to the lost and found center.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable lost-property content from the original compound candidate T1-U-017.

### T1-U-018

- Memory Location: construction-updates/temporary-parking/08-a-lot-closed
- Content: Outdoor Parking Lot A connected to the Main Building is closed during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable a-lot-closed content from the original compound candidate T1-U-018.

### T1-U-083

- Memory Location: construction-updates/temporary-parking/08-c-lot-open
- Content: During the construction period, Outdoor Parking Lot C operates as a temporary alternative parking lot for vehicles visiting the Main Building.
- Audience: All
- Baseline Relationship: Modifies the normal role of Outdoor Parking Lot C, which receives visitor vehicles, into a temporary alternative parking lot during the construction period.

### T1-U-084

- Memory Location: construction-updates/temporary-parking/08-a-lot-reopen
- Content: Outdoor Parking Lot A is planned to reopen immediately after construction on the Main Building ends.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable a-lot-reopen content from the original compound candidate T1-U-018.

### T1-U-019

- Memory Location: construction-updates/temporary-parking/09
- Content: During the construction period, the sloped access road connecting Outdoor Parking Lot A and the Main Building underground parking garage is blocked.
- Audience: All
- Baseline Relationship: Modifies the existing connection-topography information into a connection that cannot be used during the construction period.

### T1-U-054

- Memory Location: construction-updates/temporary-parking/10-explain-parking
- Content: Based on posted information, the parking guidance agent may explain the closures of the underground parking garage and Outdoor Parking Lot A and the alternative use of Outdoor Parking Lot C during the construction period.
- Audience: All
- Baseline Relationship: Modifies the existing Self Model that explained posted open status into parking change information for the construction period.

### T1-U-085

- Memory Location: construction-updates/temporary-parking/10-no-live-spaces
- Content: During the construction period, the parking guidance agent may explain the location of Outdoor Parking Lot C but cannot check or guarantee available spaces at the time of an inquiry.
- Audience: All
- Baseline Relationship: Modifies the general limitation on real-time available-space information to fit the scope of guidance for an alternative parking lot during the construction period.

### T1-U-055

- Memory Location: construction-updates/temporary-parking/11-parking-needs
- Content: A visitor accustomed to parking at the Main Building may expect to be able to enter the underground parking garage or Outdoor Parking Lot A during the construction period, drive as far as the closed access road, and then search again for Outdoor Parking Lot C.
- Audience: All
- Baseline Relationship: Modifies the normal concern about parking availability into an expectation that a familiar parking area will remain open and into renewed search behavior at the closure point.

### T1-U-064

- Memory Location: construction-updates/temporary-parking/om-delivery-crews
- Content: Delivery drivers and external maintenance contractors accustomed to unloading in Outdoor Parking Lot A may approach the same point during the construction period and then reconfirm the delivery time or unloading location at the control line.
- Audience: Visitors; Construction/Facilities Personnel
- Baseline Relationship: Modifies the normal expectation about an unloading location into an assumption that the same access will remain possible during the construction period and into behavior that reconfirms delivery conditions.

## Shops and Food Facilities · 13

### T1-U-020

- Memory Location: construction-updates/shop-updates/01-atm-closed
- Content: The ATM on the first floor of the Main Building is closed during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable atm-closed content from the original compound candidate T1-U-020.

### T1-U-088

- Memory Location: construction-updates/shop-updates/01-store-closed
- Content: The 24-hour unattended store on the first floor of the Main Building is closed during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable store-closed content from the original compound candidate T1-U-020.

### T1-U-021

- Memory Location: construction-updates/shop-updates/02-atm-alternative
- Content: During the construction period, direct users of the Main Building ATM to the ATM on the first floor of the West Complex.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable atm-alternative content from the original compound candidate T1-U-021.

### T1-U-089

- Memory Location: construction-updates/shop-updates/02-store-alternative
- Content: During the construction period, direct users of the Main Building's 24-hour store to the Campus Store in the Engineering Building between 7:00 a.m. and 11:00 p.m.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable store-alternative content from the original compound candidate T1-U-021.

### T1-U-090

- Memory Location: construction-updates/shop-updates/02-after-hours-limit
- Content: Explain that after 11:00 p.m. there is no alternative on-campus store to replace the 24-hour unattended store in the Main Building.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable after-hours-limit content from the original compound candidate T1-U-021.

### T1-U-022

- Memory Location: construction-updates/shop-updates/03-main-store
- Content: The Campus Store on the first floor of the Main Building is closed during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable main-store content from the original compound candidate T1-U-022.

### T1-U-092

- Memory Location: construction-updates/shop-updates/03-engineering-hours
- Content: During the construction period, the Campus Store in the Engineering Building operates from 7:00 a.m. to 11:00 p.m.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable engineering-hours content from the original compound candidate T1-U-022.

### T1-U-023

- Memory Location: construction-updates/shop-updates/04-cafe
- Content: The cafe on the first floor of the Main Building does not operate during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable cafe content from the original compound candidate T1-U-023.

### T1-U-025

- Memory Location: construction-updates/shop-updates/06
- Content: During the cafe closure, instruct only staff to use the coffee machine inside the first-floor Innovation Hub.
- Audience: Staff
- Baseline Relationship: Clarifies the location of the coffee machine and who may use it. This location and restriction must also be present in the pre-construction baseline.

### T1-U-026

- Memory Location: construction-updates/shop-updates/07
- Content: A student who used the Main Building ATM in the evening may expect to be able to withdraw cash at the same location during the construction period, come to the Main Building, and then have to find the West Complex ATM.
- Audience: All
- Baseline Relationship: Modifies the normal habit of evening ATM use into an expectation of continued use at the same location and into renewed search behavior for the alternative ATM.

### T1-U-056

- Memory Location: construction-updates/shop-updates/08-answer-amenities
- Content: During the construction period, the amenities guidance agent may exclude the closed Main Building ATM, unattended store, Campus Store, and cafe from recommendations and provide guidance only to posted alternative facilities.
- Audience: All
- Baseline Relationship: Modifies the existing Self Model that answered with posted locations to exclude closed facilities.

### T1-U-057

- Memory Location: construction-updates/shop-updates/09-west-atm-route
- Content: During the construction period, the route for ATM use changes from the first floor of the Main Building to the first floor of the West Complex without passing through the Main Building construction zone.
- Audience: All
- Baseline Relationship: Adds the ATM-use route changed by construction without repeating the existing separate-building location information.

### T1-U-065

- Memory Location: construction-updates/shop-updates/om-store-concessionaire-demand
- Content: The concessionaire operating the Campus Store in the Engineering Building may expect more alternative users because of the closure of Main Building facilities and seek to increase evening staffing and inventory above normal levels during the construction period.
- Audience: All
- Baseline Relationship: Modifies the normal student usage patterns known to the Main Building store concessionaire into construction-period demand and operational adjustments anticipated by the Engineering Building store concessionaire.

## Facility Operations · 17

### T1-U-027

- Memory Location: construction-updates/facility-updates/01
- Content: The Main Building undergoes major facility improvement construction during summer break.
- Audience: All
- Baseline Relationship: Retains the existing background that this is the regular facility improvement period and adds the actual construction notice.

### T1-U-028

- Memory Location: construction-updates/facility-updates/02
- Content: During the construction period, the elevators operate alternately, one at a time.
- Audience: All
- Baseline Relationship: Adds a temporary operating method not present in the existing content.

### T1-U-029

- Memory Location: construction-updates/facility-updates/03-in-person-closed
- Content: The visitor services desk suspends in-person operations during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable visitor-desk content from the original compound candidate T1-U-029.

### T1-U-099

- Memory Location: construction-updates/facility-updates/03-portal-replacement
- Content: During the construction period, visitor services are replaced by the visitor menu in the integrated campus portal.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable visitor-portal content from the original compound candidate T1-U-099.

### T1-U-030

- Memory Location: construction-updates/facility-updates/04-floor-1
- Content: The general restroom on the first floor of the Main Building cannot be used during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable floor-1-general content from the original compound candidate T1-U-030.

### T1-U-100

- Memory Location: construction-updates/facility-updates/04-floor-2
- Content: The general restroom on the second floor of the Main Building cannot be used during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable floor-2-general content from the original compound candidate T1-U-100.

### T1-U-101

- Memory Location: construction-updates/facility-updates/04-floor-3
- Content: The general restroom on the third floor of the Main Building cannot be used during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable floor-3-general content from the original compound candidate T1-U-101.

### T1-U-031

- Memory Location: construction-updates/facility-updates/05
- Content: Because the general restrooms on the first through third floors of the Main Building are closed during the construction period, the nearest general restroom changes to the exhibition hall on the third floor of the West Complex.
- Audience: All
- Baseline Relationship: Adds the nearest-alternative relationship changed by the closure of the Main Building restrooms without repeating the existing location information.

### T1-U-032

- Memory Location: construction-updates/facility-updates/06-eligible-users
- Content: During the construction period, direct students, staff, and members who cannot use the Main Building restrooms to the Central Library restrooms.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable eligible-users content from the original compound candidate T1-U-032.

### T1-U-102

- Memory Location: construction-updates/facility-updates/06-visitors
- Content: As a rule, direct general visitors who cannot use the Main Building restrooms during the construction period to restrooms outside the Main Building.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable visitors content from the original compound candidate T1-U-032.

### T1-U-033

- Memory Location: construction-updates/facility-updates/07
- Content: During the construction period, direct users who cannot use the accessible restroom in the Main Building to the Student Centre.
- Audience: All
- Baseline Relationship: Adds alternative guidance not present in the existing content.

### T1-U-104

- Memory Location: construction-updates/facility-updates/08-consultation-closed
- Content: The first-floor Innovation Hub does not operate its consultation desk during the construction period.
- Audience: All
- Baseline Relationship: Splits out the independently reviewable consultation-closed content from the original compound candidate T1-U-034.

### T1-U-035

- Memory Location: construction-updates/facility-updates/09
- Content: An Innovation Hub visitor accustomed to in-person consultation may expect to receive an immediate consultation at the first-floor desk during the construction period, see that the desk is closed, and then search again for the online consultation channel.
- Audience: Staff
- Baseline Relationship: Adds a new User Model for the possibility that a pre-construction expectation of in-person consultation will lead to a renewed search for the consultation channel when the notice about the online transition is missed.

### T1-U-037

- Memory Location: construction-updates/facility-updates/11
- Content: Air conditioning is occasionally interrupted for five to ten minutes for facility inspections.
- Audience: Staff
- Baseline Relationship: Adds an operational notice not present in the existing content while excluding the detailed construction scope.

### T1-U-038

- Memory Location: construction-updates/facility-updates/12
- Content: The construction period runs from June 24 through August 23.
- Audience: All
- Baseline Relationship: Adds the confirmed start and end dates to the existing summer-break construction guidance.

### T1-U-106

- Memory Location: construction-updates/facility-updates/14-no-private-scope
- Content: During the construction period, the facility guidance agent's response scope is limited to publicly disclosed operational impacts and it cannot verify or infer nonpublic types of work.
- Audience: All
- Baseline Relationship: Adds a specific temporary scope of answering only about public operational impacts during the construction period, based on the general limitation on nonpublic information.

### T1-U-066

- Memory Location: construction-updates/facility-updates/om-service-contractors
- Content: Cleaning and security contract staff may find the designated service entrance during the construction period more burdensome than the familiar lobby shift change and may go to the wrong entrance at the start of a shift.
- Audience: Staff; Construction/Facilities Personnel
- Baseline Relationship: Modifies the normal preference for separate routes into the burden of the new service entrance during the construction period and the possibility of early confusion.

## Route Changes · 9

### T1-U-040

- Memory Location: construction-updates/route-changes/01
- Content: The indoor route that passed through the first through third floors of the Main Building to the Central Library cannot be used during the construction period.
- Audience: All
- Baseline Relationship: Modifies the existing content stating that passage is possible.

### T1-U-041

- Memory Location: construction-updates/route-changes/02
- Content: The route from the third-floor rear entrance to the Central Library is closed during the construction period.
- Audience: All
- Baseline Relationship: Modifies the existing content stating that the route is open.

### T1-U-042

- Memory Location: construction-updates/route-changes/03
- Content: The Outdoor Parking Lot A–Main Building–Central Library route is closed during the construction period.
- Audience: All
- Baseline Relationship: Modifies the existing content stating that it is a fast, open route.

### T1-U-043

- Memory Location: construction-updates/route-changes/04
- Content: A student who prefers the air-conditioned indoor route through the Main Building in summer may experience substantial heat and travel burden when redirected to an outdoor alternative route during the construction period.
- Audience: All
- Baseline Relationship: Modifies the normal preference for an air-conditioned indoor route into the heat and burden expected from outdoor travel during the construction period.

### T1-U-045

- Memory Location: construction-updates/route-changes/06
- Content: When providing directions to the accessible restroom in the Student Centre during the construction period, instruct users to take the accessible route to the left as viewed from the Main Building.
- Audience: All
- Baseline Relationship: Adds this by combining it with the alternative-route information for the Student Centre and Outdoor Parking Lot C.

### T1-U-047

- Memory Location: construction-updates/route-changes/08
- Content: During the construction period, the designated alternative accessible route to the Central Library is Outdoor Parking Lot C–Student Centre accessible entrance–Central Library west entrance.
- Audience: All
- Baseline Relationship: Adds a new role as the official alternative route during the construction period without repeating existing route facts.

### T1-U-059

- Memory Location: construction-updates/route-changes/09
- Content: During the construction period, the Central Library west entrance is designated as the official alternative entrance for the closed connecting route through the Main Building.
- Audience: All
- Baseline Relationship: Removes the retained fact of normal operation and adds the designation as the official alternative entrance during the construction period.

### T1-U-060

- Memory Location: construction-updates/route-changes/10-guide-routes
- Content: During the construction period, the route guidance agent may exclude from comparison candidates closed routes that pass through the first through third floors of the Main Building, the third-floor rear entrance, or Outdoor Parking Lot A.
- Audience: All
- Baseline Relationship: Modifies the existing Self Model that compared stored topographical information to exclude routes closed during the construction period.

### T1-U-067

- Memory Location: construction-updates/route-changes/om-mobility-support-companion
- Content: If the indoor shortcut through the Main Building is closed during the construction period, a mobility-support companion may reconfirm the distance and slope of the alternative accessible route before accompanying the user.
- Audience: All
- Baseline Relationship: Modifies a mobility-support companion's normal preference for indoor routes into behavior that reconfirms in advance the distance and slope of the alternative accessible route during the construction period.
