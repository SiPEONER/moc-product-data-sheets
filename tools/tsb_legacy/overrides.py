"""Per-bulletin fixes on top of the edit rules (keys are bulletin ids)."""
import pathlib

_bmw = [l.split("|", 1) for l in (pathlib.Path(__file__).parent / "bmw.txt").read_text().splitlines() if "|" in l]

OVERRIDES = {
    "11-19": {"title": "Basic Training and Troubleshooting Seminar", "tag": "Notice", "category": "Equipment",
              "lead": "The Machine and Equipment Department scheduled a Basic Troubleshooting Seminar for January 26 and 27, 2012, covering proper equipment operation and basic equipment troubleshooting.",
              "body": ["Maximum of 10 attendees. Previous attendees of this class did not need to attend. Reservations closed Monday, January 9, 2012."]},
    "12-04": {"title": "Power Steering Fluid 06181 and Revised Formula 01231", "tag": "New", "pn": ["06181", "01231"]},
    "13-08": {"title": "Volkswagen Transmission Adapter for Automatic-Transmission Service", "tag": "New"},
    "15-03": {"title": "Smart Tech II Automatic Transmission Fluid Exchanger Machine", "tag": "New"},
    "18-02": {"title": "Air Coolant Machine", "tag": "New", "category": "Cooling", "pn": ["95330"],
              "lead": "The Air Coolant Machine (Model 95330) was issued as this bulletin. The original flyer is attached as issued.",
              "parts": [["95330", "Air Coolant Machine", ""]]},
    "19-EN1": {"volno": "Equipment Notice, April 2019", "title": "GDI Service for Nissan Vehicles", "tag": "Notice", "category": "Fuel",
               "lead": "Some EDR-3 machines go into limp mode while performing GDI services on Nissan vehicles with the engine at 3,000 RPM, normally within 3 to 5 minutes of starting the service.",
               "body": ["To prevent the vehicle from going into limp mode, perform the service at 1,000 RPM."]},
    "19-EN2": {"volno": "Equipment Notice, May 2019", "title": "EDR-3 Firmware Update v.1.9", "tag": "Notice", "category": "Fuel", "pn": ["71247"],
               "lead": "An important update that must be installed in all EDR-3 machines and modules as soon as possible.",
               "body": ["What's changing: when choosing an induction or GDI service, the customer is asked to enter the engine size (for example 4, 6 or 8 cylinders). The EDR-3 then uses a strategy specific to that engine size.",
                        "What you need to do: the firmware is available by email, or order a USB drive (part 71247) and ask for the firmware to be preloaded before it ships. Contact the Equipment Department."],
               "parts": [["71247", "USB drive with EDR-3 firmware v.1.9 preloaded", "Ask for the firmware to be preloaded"]]},
    "12-09": {"tag": "Superseded", "note": "Superseded by Vol. 12 No. 10 (April 26, 2012), which withdraws this RPM change: perform Optimizer services per the 16501 label and do not exceed 2000 RPM."},
    "12-10": {"tag": "Notice", "title": "Optimizer Service Procedure Update", "supersedes": ["Vol. 12 No. 09"]},
    "14-09": {"note": "The original prints this bulletin as Vol. 14 No. 08; it is filed as No. 09."},
    "14-11": {"note": "The original prints this bulletin as Vol. 14 No. 10; it is filed as No. 11."},
    "16-01": {"drop_attachments": True,
              "table": {"title": "Known to fit (BMW, 96134)", "head": ["Years", "Model"], "rows": [[a.strip(), b.strip()] for a, b in _bmw]}},
}

OVERRIDES.update({
    "11-07": {"lead": "MOC has developed a new Misting Gun with an air regulator for use with Odor-B-Gone. It is now available to order.",
              "body": ["Odor-B-Gone (Unscented, 0650; New Car Scent, 0651) is sold separately.",
                       "You can convert a current Misting Gun to the Air Regulator model with these parts: Regulator Adapter 74359, Air Regulator 74449, Pressure Gauge 75601 and QD Adapter 94254.",
                       "Remove the existing QD adapter from the bottom of the Misting Gun before adding the Air Regulator. Keep the o-ring that comes with the misting gun and install it above the Regulator Adapter (74359)."],
              "pn": ["74360"], "captions": {0: "Universal Misting Gun w/Regulator", 1: "", 2: ""},
              "parts": [["74360", "Universal Misting Gun w/Regulator", ""], ["0650", "Odor-B-Gone (Unscented)", "Sold separately"], ["0651", "Odor-B-Gone (New Car Scent)", "Sold separately"],
                        ["74359", "Regulator Adapter", "Conversion part"], ["74449", "Air Regulator", "Conversion part"], ["75601", "Pressure Gauge", "Conversion part"], ["94254", "QD Adapter", "Conversion part"]]},
    "11-10": {"lead": "The lever on the Universal Drain Plug Oil Adapter (74741) can work loose, because the set screw in the Retainer Lever gets retightened again and again and can strip the threads inside the lever. MOC now makes the Long Retainer Lever out of steel instead of aluminum.",
              "body": ["If your Universal Drain Plug Adapter has this problem, contact the Machine and Equipment Department with the subject \"74741 Replacement Lever\", your name and phone number, and your shipping address. A replacement lever will be shipped to you."],
              "steps": ["Note which way the lever is facing, then remove the aluminum lever by unscrewing the set screw.",
                        "Discard the aluminum lever and attach the new steel lever in the same location with the original set screw."],
              "note": "Attach the new lever facing the same direction as the one you removed, with the set screw hole in the lever aligned with the flat spot on the retainer.",
              "benefits": [], "captions": {1: "Retainer Lever", 2: "", 3: "Flat spot on the retainer must face the set screw hole"}},
    "12-03": {"lead": "Kit 09221 Optimizer/zMax is now available: a powerful combination for excellent results.",
              "body": ["The MOC Optimizer (16501) process cleans carbon from problem areas of the fuel-induction system, while zMax (09108) addresses fuel deposits as a tank additive and completes the cleaning process. It has proven a quick and easy fix for carbon-related issues on direct-injected vehicles."],
              "steps": ["Bring the vehicle to operating temperature. Shake the can well. With the engine running, locate a manifold vacuum line that evenly feeds all cylinders (Figure A). Bring engine speed up to 2000 RPM.",
                        "Insert the extension tip of the Optimizer (16501) can into the vacuum line (Figure B) and evacuate the product until the can is empty. If the engine starts to sputter, reduce the flow to avoid stalling. When the can is empty, reconnect the vacuum line.",
                        "Pour the bottle of zMax (09108) into the fuel tank. For maximum efficiency the tank should be at least half full."],
              "note": "If the engine stalls during application, stop evacuating the can and turn the crankshaft over several times before restarting. With an electronic throttle body, you need two people or a tool to hold 2000 RPM.",
              "captions": {0: "Kit 09221", 1: "Figure A", 2: "Figure B"},
              "parts": [["09221", "Kit, Optimizer/zMax", ""], ["16501", "Optimizer", "In the kit"], ["09108", "zMax", "In the kit"]]},
    "14-06": {"body": [], "captions": {0: "Adapters: 1/4\" 95666, 3/8\" 95667, 1/2\" 95668, 3/8\" nylon 95669"},
              "parts": [["95644", "Differential Adapter Kit", ""], ["95666", "Adapter, Differential, 1/4\" Open Hose (Dekabon)", ""], ["95667", "Adapter, Differential, 3/8\" Open Hose (Dekabon)", ""],
                        ["95668", "Adapter, Differential, 1/2\" Open Hose (Dekabon)", ""], ["95669", "Adapter, Differential, 3/8\" Open Hose (Nylon)", ""]]},
    "14-09": {"title": "Technical Service Line Hours Extended", "tag": "Notice", "category": "Equipment",
              "lead": "The Technical Service Line (866.244.6621) is now available from 6:00 am PST (instead of 7:00 am PST) to 5:00 pm PST, or longer depending on advisor availability.",
              "body": ["The extended hours began Monday, August 18, 2014."], "note": "The original prints this bulletin as Vol. 14 No. 08; it is filed as No. 09."},
    "14-14": {"body": ["The 72409 adapter is discontinued and replaced by the 72416 adapter. The 74500 adapter is discontinued and replaced by the 75021 adapter."],
              "captions": {0: "Valve Style Adapter, Fuel Injector (used on the 74000 machine)", 1: "Puncture Adapter, Fuel Injector (used on the 75000 machine)"},
              "pn": ["72416", "75021"],
              "parts": [["72416", "Valve Style Adapter, Fuel Injector", "74000 machine; replaces 72409"], ["75021", "Puncture Adapter, Fuel Injector", "75000 machine; replaces 74500"]]},
    "15-15": {"body": ["Replacement parts are available for these adapters (see the part numbers below)."],
              "steps": ["To remove the current O-ring, use a pick-style tool (Fig. 1) and gently insert it behind the O-ring to pull it out of the O-ring gland (Fig. 2). Be careful not to scratch the exposed surfaces of the adapter interior.",
                        "Place the new O-ring (MOC-approved O-rings only) into the adapter horizontally, on top of the angled surface above the O-ring gland (Fig. 3). With a small screwdriver (Fig. 4), gently push the O-ring in until one edge catches under the lip of the gland, then push it into the gland until it is held in place (Fig. 5). Avoid scratching the interior surfaces.",
                        "Push the opposite side of the O-ring down until it is caught by the edge of the gland (Fig. 6), then work the rest of the O-ring into the gland the same way until it is firmly seated.",
                        "Insert the matching male adapter to verify the O-ring is seated properly before starting a service."],
              "benefits": [], "pn": ["73048", "73060", "73059"],
              "captions": {0: "3/8\" Female QD (73048), 5/16\" Female QD (73060), 5/16\" Female 90° QD (73059)", 1: "Fig. 1", 2: "Fig. 2", 3: "Fig. 3", 4: "Fig. 4", 5: "Fig. 5", 6: "Fig. 6"},
              "parts": [["73048", "Adapter, Fuel, 3/8\" Female QD", ""], ["73060", "Adapter, Fuel, 5/16\" Female QD", ""], ["73059", "Adapter, Fuel, 5/16\" Female 90° QD", ""],
                        ["94736", "Spring Clip", "3/8\" QD adapter"], ["73058", "O-ring (1 pc)", "3/8\" QD adapter"], ["73062", "O-ring (25 pk)", "3/8\" QD adapter"],
                        ["73056", "Spring Clip", "5/16\" QD adapter"], ["73057", "O-ring (1 pc)", "5/16\" QD adapter"], ["73061", "O-ring (25 pk)", "5/16\" QD adapter"]]},
    "18-04": {"title": "Power Braking Warning Decal Kit", "pn": ["94423"],
              "lead": "Some technicians have been power braking while performing transmission fluid changes with MOC equipment. Power braking with the car running can damage MOC transmission service equipment. A kit of warning decals is now available to add to transmission service machines in the field (Kit 94423).",
              "body": ["Review the materials with all service technicians and other users of the equipment. MOC strongly recommends that technicians inspect all hoses, crimps, adapters and related components before every service, and that field personnel inspect them during routine visits. Check each machine for power braking damage before installing the warning decal."],
              "steps": ["External red and black service hoses: check both ends of each hose for swelling before the clamp or ferrule (Figure 1).",
                        "Check that the fitting crimped or clamped to each hose end is not loose and has not pulled away from the hose, exposing the barbed fitting.",
                        "Grab each fitting and try to twist it. If it spins inside the tubing, the connection is too loose and there may be damage.",
                        "Feel the length of the hose: it should not feel spongy or squishy. Check the color; heat damage changes the color of the hose. Check that the diameter is consistent along the whole length.",
                        "Open the machine and inspect the interior hoses the same way: swelling at the clamp (Figure 2), loose fittings that twist, a spongy feel or changed color."],
              "benefits": [], "captions": {0: "Figure 1: fitting flush against the hose end, diameter consistent (good); fitting pulled away with barb exposed, hose swollen at the ferrule (damaged)", 1: "Figure 2: interior hoses, good and damaged", 2: ""},
              "parts": [["94423", "Kit, Power Braking Warning Decal", "For machines in the field"]]},
    "18-17": {"steps": ["Unscrew the cone of the adapter from the hex fitting connector, then unscrew the misting nozzle from the hex fitting connector.",
                        "Unscrew the filter from the back of the misting nozzle.",
                        "Remove the spring and poppet from the head of the misting nozzle.",
                        "Clean the nozzle head: carefully spray parts wash into the head of the nozzle body, followed by a couple of quick bursts of shop air through the front of the nozzle. You should see light through the nozzle tip when it is clean.",
                        "Reassemble the spring and poppet in reverse order from step 3, with the spring around the base of the poppet, and make sure the head of the poppet goes into the head of the nozzle.",
                        "Screw the misting nozzle into the hex fitting by hand until tight, then tighten an additional 1 to 2 turns with a wrench."],
              "body": []},
    "21-02": {"lead": "MOC has created two new adapters that make induction services easier with the EDR-3 machine through the MAP sensor port, keeping the MAP sensor connected to the vehicle during the service. This may help hold the engine at the recommended RPM.",
              "body": ["These adapters can only be used with the EDR-3 machines."], "pn": ["73448", "73449"],
              "captions": {0: "", 1: "Adapter, MAP Sensor, 90 Degree (73448) and Straight (73449)"},
              "parts": [["73448", "Adapter, MAP Sensor, 90 Degree", "EDR-3 only"], ["73449", "Adapter, MAP Sensor, Straight", "EDR-3 only"]]},
})

OVERRIDES.update({
    "12-05": {"title": "Accelerator Pedal Depressor"},
    "12-19": {"title": "12mm Quick Disconnect Fuel Adapter"},
    "11-18": {"title": "Optimizer Tools for BMW, Audi and Volkswagen"},
    "12-17": {"title": "Universal 20in Optimizer Tool"},
    "13-03": {"title": "15in Optimizer Tool"},
    "13-27": {"title": "Optimizer Tool for BMW Twin Turbo Engines"},
    "12-10": {"tag": "Notice", "supersedes": ["Vol. 12 No. 09"], "title": "Optimizer Service Procedure Update", "lead": "This bulletin supersedes Vol. 12 No. 9: further in-house testing found that the catalytic converter stays within normal operating temperature during an Optimizer service at 2000 RPM, as originally instructed. Disregard Vol. 12 No. 9.",
              "body": ["Perform all Optimizer services per the directions on the 16501 label, and do not exceed 2000 RPM.", "The Optimizer \"Do-It-Right\" documents have been revised to match. MOC highly recommends giving them to every account that purchases Optimizer."]},
    "13-04": {"body": ["To tell the old hose connector from the new one on the Green Service Hose (94841), look at the tip of the hose connector: the old connector has a blue plastic tip, the new connector has a metal tip."]},
})

OVERRIDES.update({
    "17-07": {"body": ["Both adapters are used together with the existing Lexus banjo pressure-port adapter (94778) to perform a service."]},
    "15-06": {"body": ["The photos show the OEM quick disconnects on Ford and Audi vehicles that these adapters connect to."]},
    "16-14": {"body": ["The old filter screen inside the manifold is discontinued and replaced by this inline filter. Photos are for reference.",
                       "Smart Tech II: the filter goes on the New Fluid hose inside the machine, between the diverter valve and the New Fluid tank (Fig. 1). Locate the hose coming up through the chassis from the New Fluid tank (Fig. 2), measure about 10in from the chassis surface and cut the hose. Install the filter between the cut ends with a pinch clamp (94098) on each side (Fig. 3). The arrow stamped on the filter must point toward the diverter valve.",
                       "Standard ATF machine: the filter goes on the New Fluid hose inside the machine, between the 3-way valve and the New Fluid tank (Fig. 4). Remove the hose and the 45° hose barb from the tee fitting on the 3-way valve (Fig. 5) and replace the barb with a straight barb fitting (94071). Cut 2in off the end of the black hose and reattach it to the barb, then install the filter between the 2in piece and the hose (Fig. 6). The arrow stamped on the filter must point toward the 3-way valve."]},
})
PART_DESC = {
    "12-04": {"03771": "Tech Grade Power Steering Service Kit (2-pack)", "2161": "Power Steering Service Kit"},
    "12-09": {"83752": "Optimizer \"Do It Right\" booklet"},
    "12-33": {"98026": "Filter, brake service hose"},
    "13-26": {"98769": "Replacement Washer Kit (5 pk)"},
    "13-36": {"73051": "Seal Replacement Kit, 1/2in Ford fuel adapters and plugs", "73052": "Seal Replacement Kit, Ford fuel adapters and plugs"},
    "14-05": {"96500": "Multi-Fluid Machine"},
    "14-07": {"72232": "Adapter, 1/2in Open Hose", "94693": "Adapter, Ford 90° ATF Quick Disconnect"},
    "14-18": {"72166": "Adapter, Mercedes V6 Twin Turbo (276 engine)", "72167": "Adapter, Mercedes V8 Turbo (278 engine)"},
    "14-19": {"94342": "Adapter, Coolant, Male, Ford Focus", "94343": "Adapter, Coolant, Ford Focus"},
    "14-20": {"72325": "Dodge 6.7L EGR Valve & Cooler Cleaning Kit"},
    "16-03": {"94916": "GM ATF Adapter Kit"},
    "17-08": {"94939": "Laminated flyer, pressure-port transmission services"},
    "20-02": {"94951": "High Flow Double Pump Replacement Kit"},
}

DROP_PARAS = {}

# Figures that are only the old printed header (company name, TSB number, date) as a picture
for _id, _idx in {"11-10": [1], "12-24": [0], "12-25": [2]}.items():
    OVERRIDES.setdefault(_id, {}).setdefault("drop_figs", []).extend(_idx)
OVERRIDES["11-10"]["drop_figs"].append(3)  # crop of the original page text, not a photo
OVERRIDES["16-14"]["parts"] = [["94921", "Inline filter", ""], ["94098", "Pinch clamp", "Smart Tech II"], ["94071", "Straight barb fitting", "Standard ATF machine"]]
OVERRIDES["16-01"]["body"] = ["This adapter is now available for purchase."]
