from typing import Dict, Tuple

new_private_dictionaries: Dict[str, Dict[int, Tuple[str, str, str, str]]] = {
    "Accuray Robotic Control": {
        0x300F1001: ("CS", "1", "Use Increased Pitch Correction", ""),  # noqa
    },
    "SagiPlan": {
        0x10011000: ("UL", "1", "Irradiation Data Check Sum 1", ""),  # noqa
        0x10011001: ("UL", "1", "Irradiation Data Check Sum 2", ""),  # noqa
        0x10011005: ("DT", "1", "Study Last Saved", ""),  # noqa
        0x10011006: ("UL", "1-n", "Treat in Fraction", ""),  # noqa
        0x10011009: ("DS", "1", "Dwell Position from Tip", ""),  # noqa
        0x1001100A: ("ST", "1", "Reference to Applicator Database", ""),  # noqa
    },
    "Brainlab - ONC - Beam Parameters": {
        0x300B1210: ("IS", "1-n", "Referenced Beam List", ""),  # noqa
    },
    "Brainlab - ONC - Multi-axial treatment machine": {
        0x320B1001: ("CS", "1", "Dynamic Tracking", ""),  # noqa
    },
    "GEMS_PETD_01": {
        0x0009100D: ("DT", "1", "GE PET Scan Time", ""),  # noqa
    },
    "IBA": {
        0x300D1002: ("SH", "1", "IBA Scattered Mode", ""),  # noqa
    },
    "IMPAC": {
        0x300B1002: ("FL", "1", "Maximum Collimated Field Diameter", ""),  # noqa
        0x300B1004: ("FL", "1", "Planned Distal Target Distance", ""),  # noqa
        0x300B100E: ("FL", "1", "Nominal SOBP Width", ""),  # noqa
        0x300B1020: ("DS", "2", "Respiratory Phase Gating Duty Cycle", ""),  # noqa
        0x300B1090: ("SH", "2", "Line Spot Tune ID", ""),  # noqa
        0x300B1092: ("IS", "1", "Number of Line Scan Spot Positions", ""),  # noqa
        0x300B1094: ("FL", "2-n", "Line Scan Position Map", ""),  # noqa
        0x300B1096: ("FL", "2-n", "Line Scan Meterset Weights", ""),  # noqa
        0x300B1098: ("FL", "2", "Line Scanning Spot Size", ""),  # noqa
        0x300B109A: ("IS", "1", "Number of Line Scan Paintings", ""),  # noqa
        0x30091001: ("FL", "1", "Measured Distal Target Distance", ""),  # noqa
        0x30091002: ("FL", "1", "Specified Primary Ambient Meterset", ""),  # noqa
        0x30091003: ("FL", "1", "Delivered Primary Ambient Meterset", ""),  # noqa
        0x30091004: ("FL", "1", "Current Temperature", ""),  # noqa
        0x30091005: ("FL", "1", "Current Pressure", ""),  # noqa
        0x30091006: ("FL", "1", "TP Correction Factor", ""),  # noqa
        0x30091007: ("FL", "1", "Measured Uncollimated Field Diameter", ""),  # noqa
        0x30091008: ("FL", "1", "Measured SOBP Width", ""),  # noqa
        0x30091010: ("FL", "1", "Table Top Vertical Correction", ""),  # noqa
        0x30091011: ("FL", "1", "Table Top Longitudinal Correction", ""),  # noqa
        0x30091012: ("FL", "1", "Table Top Lateral Correction", ""),  # noqa
        0x30091013: ("FL", "1", "Patient Support Angle Correction", ""),  # noqa
        0x30091014: ("FL", "1", "Patient Support Pitch Angle Correction", ""),  # noqa
        0x30091015: ("FL", "1", "Patient Support Roll Angle Correction", ""),  # noqa
        0x30091016: ("IS", "1", "Number of Paintings Fully Delivered", ""),  # noqa
        0x30091017: ("IS", "1", "Treatment Termination Scan Spot Index", ""),  # noqa
        0x30091047: ("FL", "2-n", "Line Scan Metersets Delivered", ""),  # noqa
        0x300B1001: ("FL", "1", "Distal Target Distance Tolerance", ""),  # noqa
        0x300B1003: ("CS", "1", "Beam Check Flag", ""),  # noqa
        0x300B1005: ("CS", "1", "Treatment Delivery Status", ""),  # noqa
        0x300B1006: ("CS", "1", "Treatment Machine Mode", ""),  # noqa
        0x300B1007: ("CS", "1", "Position Correction Flag", ""),  # noqa
        0x300B1008: ("SH", "1", "Beam Line Data Table Version", ""),  # noqa
        0x300B1009: ("CS", "1", "Respiratory Gating Flag", ""),  # noqa
        0x300B100A: ("FL", "1", "Respiratory Gating Cycle", ""),  # noqa
        0x300B100B: ("FL", "1", "Flat Top Length", ""),  # noqa
        0x300B100C: ("FL", "1", "Spill Length", ""),  # noqa
        0x300B100D: ("FL", "1", "Uncollimated Field Diameter Tolerance", ""),  # noqa
        0x300B1011: ("FL", "1", "Nominal SOBP Width Tolerance", ""),  # noqa
        0x300B1012: ("FL", "1", "TP Corrected Meterset Tolerance", ""),  # noqa
        0x300B1013: ("IS", "1", "Number of Pieces", ""),  # noqa
        0x300B1014: ("FL", "1-n", "Change Check Data Before", ""),  # noqa
        0x300B1015: ("FL", "1-n", "Change Check Data After", ""),  # noqa
        0x300B1016: ("FL", "1", "Beam Intensity", ""),  # noqa
        0x300B1017: ("FL", "1", "Peak Range", ""),  # noqa
        0x300B1018: ("DS", "1", "Planned Patient Support Angle", ""),  # noqa
        0x300B101A: ("FL", "1", "Planned Table Top Roll Angle", ""),  # noqa
    },
    "medPhoton 1.0": {
        0x30BB1000: ("SH", "1", "Patient Setup ID", ""),  # noqa
        0x30BB1001: ("SH", "1", "Imaging Protocol ID", ""),  # noqa
        0x30BB1022: ("DS", "2", "Patient Support Angle Offset Interval", ""),  # noqa
        0x30BB102C: ("DS", "6", "Isocenter Position Offset Interval", ""),  # noqa
        0x30BB1040: ("DS", "2", "Table Top Pitch Angle Offset Interval", ""),  # noqa
        0x30BB1044: ("DS", "2", "Table Top Roll Angle Offset Interval", ""),  # noqa
    },
    "Philips PET Private Group": {
        0x70531000: ("DS", "1", "Philips SUV Scale Factor", ""),  # noqa
        0x70531009: ("DS", "1", "Philips Activity Concentration ScaleFactor", ""),  # noqa
    },
    "RAYSEARCHLABS 2.0": {
        0x40011001: ("DT", "1", "Treatment Machine CommissionTime", ""),  # noqa
        0x40011002: ("ST", "1", "RBE Model Name", ""),  # noqa
        0x40011003: ("DT", "1", "RBE Model Commission Time", ""),  # noqa
        0x40011004: ("FL", "1", "Block Milling Tool Diameter", ""),  # noqa
        0x40011005: ("FL", "1", "Spill Length", ""),  # noqa
        0x40011006: ("FL", "1", "Degrader", ""),  # noqa
        0x40011007: ("FL", "1", "Particles Per Spill", ""),  # noqa
        0x40011008: ("DS", "1", "CNAO Nominal Beam Energy", ""),  # noqa
        0x40011009: ("DS", "1", "CNAO Nominal Beam Energy ScaleFactor", ""),  # noqa
        0x40011010: ("ST", "1", "Tissue Name", ""),  # noqa
        0x40011011: ("DS", "1", "Target Prescription Effective Dose", ""),  # noqa
        0x40011012: ("SH", "1", "Internal Treatment Machine Name", ""),  # noqa
        0x40011014: ("ST", "1", "RBE Cell Type Name", ""),  # noqa
        0x40011015: ("DS", "1", "Planned Blood Boron Concentration", ""),  # noqa
        0x40011016: ("OB", "1", "ROI Index Pixel Data", ""),  # noqa
        0x40011017: ("US", "1", "ROI Index Bits Allocated", ""),  # noqa
        0x40011020: ("LO", "1", "Tomo IDMS Machine ID", ""),  # noqa
        0x40011021: ("LO", "1", "Tomo IDMS Beam ID", ""),  # noqa
        0x40011022: ("DS", "3", "Tomo Localization point", ""),  # noqa
        0x40011023: ("DS", "3", "Tomo Beam Isocenter", ""),  # noqa
        0x40011025: ("IS", "1", "Tomo machine revision", ""),  # noqa
        0x40011026: ("IS", "1", "Tomo beam revision", ""),  # noqa
        0x40011027: ("DS", "1", "Tomo intended back jaw position", ""),  # noqa
        0x40011028: ("DS", "1", "Tomo intended front jaw position", ""),  # noqa
        0x40011029: ("ST", "1", "Beam Dose Specification PointName", ""),  # noqa
        0x4001102A: ("UI", "1", "Tomo Plan SOP Instance UID", ""),  # noqa
        0x40011030: ("SH", "1", "Reference Beam Data ID", ""),  # noqa
        0x40011031: ("DS", "1", "Reference Depth in Water", ""),  # noqa
        0x40011032: ("DS", "1", "Mitsubishi Reference Value", ""),  # noqa
        0x40011033: ("CS", "1", "Treatment Machine RBE Mode", ""),  # noqa
        0x40011040: ("SQ", "1", "ROI Contour Sequence", ""),  # noqa
        0x40011041: ("LO", "1", "Contour Name", ""),  # noqa
        0x40011042: ("ST", "1", "Contour Description", ""),  # noqa
        0x40011043: ("CS", "1", "Contour Generation Algorithm", ""),  # noqa
        0x40011044: ("CS", "1", "Contour Interpreted Type", ""),  # noqa
        0x40011045: ("IS", "3", "Contour Display Color", ""),  # noqa
        0x40011046: ("IS", "1", "Number of Contour Points", ""),  # noqa
        0x40011047: ("OF", "2-2n", "Contour Data", ""),  # noqa
        0x40011048: ("IS", "1", "Number of Pixel Contour Points", ""),  # noqa
        0x40011049: ("OF", "1", "Pixel Contour Data", ""),  # noqa
        0x40011050: ("UI", "1", "Referenced Structure Set SOPInstance UID", ""),  # noqa
        0x40011051: ("IS", "1", "Referenced ROI Number", ""),  # noqa
        0x40011052: ("SQ", "1", "Contour Data Sequence", ""),  # noqa
        0x40011053: ("DS", "1", "Tomo Projection Time", ""),  # noqa
        0x40011054: ("DS", "1", "Applicator Thickness", ""),  # noqa
        0x40011055: ("IS", "1", "Number Of Aperture Contour Points", ""),  # noqa
        0x40011056: ("FL", "2-2n", "Aperture Contour Point Map", ""),  # noqa
        0x40011057: ("CS", "1", "Collimation Mode", ""),  # noqa
        0x40011060: ("LO", "1", "RaySearch Checksum AlgorithmVersion", ""),  # noqa
        0x40011061: ("OB", "1", "RaySearch Checksum Data", ""),  # noqa
        0x40011062: ("SQ", "1", "Tracking ROI Sequence", ""),  # noqa
        0x40011063: ("DS", "1-6", "Imaging Angles", ""),  # noqa
        0x40011064: ("OB", "1", "Mevion SMC Output", ""),  # noqa
        0x40011065: ("LO", "1", "Mevion SMC Version", ""),  # noqa
        0x40011066: ("DS", "1", "Tomo Couch Insertion Position Y", ""),  # noqa
        0x40011067: ("DA", "1", "Consent Expiry Date", ""),  # noqa
        0x40011068: ("FL", "1", "Tomo Projection Time FL", ""),  # noqa
        0x40011070: ("DT", "1", "Source Commission Time", ""),  # noqa
        0x40011071: ("DT", "1", "Application Setup Commission Time", ""),  # noqa
    },
    "SIEMENS MED SYNGO RT": {
        0x300B1010: ("CS", "1", "Plan Type", ""),  # noqa
        0x300B1012: ("LO", "1", "Imager Organ Program", ""),  # noqa
        0x300B1020: ("SQ", "1", "Alternative Treatment MachineName Sequence", ""),  # noqa
        0x300B1024: ("DS", "1", "Imager Angular Angle", ""),  # noqa
        0x300B1025: ("DS", "1", "Imager Iso-centric Angle", ""),  # noqa
        0x300B1026: ("DS", "1", "Imager Vertical Position", ""),  # noqa
        0x300B1027: ("DS", "1", "Imager Longitudinal Position", ""),  # noqa
        0x300B1028: ("DS", "1", "Imager Lateral Position", ""),  # noqa
        0x300B1029: ("DS", "1", "Imager Angular Rotation Direction", ""),  # noqa
        0x300B102A: ("DS", "1", "Imager Isocentric Rotation Direction", ""),  # noqa
        0x300B102C: ("DS", "1", "Imager Orbital Angle", ""),  # noqa
        0x300B102E: ("CS", "1", "Imaging Technique", ""),  # noqa
        0x300B102F: ("DS", "1", "Imager Orbital Rotation Direction", ""),  # noqa
        0x300B1076: ("CS", "1", "Fraction Group Code", ""),  # noqa
        0x300B1077: ("IS", "1", "Referenced Treatment BeamNumber", ""),  # noqa
        0x300B1078: ("DS", "1", "Fraction Dose to Dose Reference", ""),  # noqa
        0x300B10A1: ("OB", "1", "Checksum Encryption Code", ""),  # noqa
        0x300B10E5: ("OB", "1", "Configuration Baseline", ""),  # noqa
    },
    "TOMO_DD_01": {
        0x300D2010: ("SH", "1", "Procedure Number", ""),  # noqa
        0x300D2011: ("CS", "1", "Procedure Type", ""),  # noqa
        0x300D2012: ("CS", "1", "Procedure Purpose", ""),  # noqa
        0x300D2020: ("IS", "1", "Detector channel count", ""),  # noqa
        0x300D2021: ("IS", "1", "Dataset length", ""),  # noqa
        0x300D2022: ("DS", "1", "Detector data scaling factor", ""),  # noqa
        0x300D2024: ("CS", "1", "Compression Type", ""),  # noqa
        0x300D2025: ("IS", "1", "Compression Factor", ""),  # noqa
        0x300D2026: ("SQ", "1", "Active Projection Beam Sequence", ""),  # noqa
        0x300D2030: ("CS", "1", "Detector unit of measure", ""),  # noqa
        0x300D2031: ("DS", "1", "Element width", ""),  # noqa
        0x300D2032: ("DS", "1", "Curvature radius", ""),  # noqa
        0x300D2033: ("DS", "1", "Surface to Axis Distance", ""),  # noqa
        0x300D2034: ("DS", "1", "Surface to Center Distance", ""),  # noqa
        0x300D2035: ("IS", "2", "Channel range", ""),  # noqa
    },
    "TOMO_HA_01": {
        0x300D1010: ("CS", "1", "Tomo Structure Blocking", ""),  # noqa
        0x300D1012: ("IS", "1", "Tomo Overlap Precedence", ""),  # noqa
        0x300D1014: ("DS", "1", "Tomo Modulation Factor", ""),  # noqa
        0x300D1016: ("IS", "1", "Tomo Target Minimum Dose Penalty", ""),  # noqa
        0x300D1017: ("IS", "1", "Tomo Target Maximum Dose Penalty", ""),  # noqa
    },
}
