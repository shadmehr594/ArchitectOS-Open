# ==========================================================
# ArchitectOS Site Constraint Model v1.1
#
# Site Intelligence Layer
#
# Site
#  |
#  ↓
# Constraints
#  |
#  ↓
# Zoning / BIM / CAD / Regulation
#
# ==========================================================


class SiteConstraintModel:


    VERSION = "1.1"



    def __init__(self):

        self.constraints = {


            # جهت گیری زمین
            "orientation": {},


            # عقب نشینی ها
            "setbacks": {},


            # حیاط ها و فضاهای باز
            "yards": {},


            # فضاهای باز عمومی
            "open_spaces": [],


            # سطح اشغال
            "coverage": None,


            # تراکم
            "density": None,


            # مساحت قابل ساخت
            "buildable_area": None,


            # موقعیت قرارگیری ساختمان در زمین
            "building_position": None,


            # نورگیرها
            "light_wells": [],


            # دسترسی
            "access": {},


            # محدودیت های پارکینگ
            "parking_constraints": {},


            # ضوابط اختیاری
            "regulations": {}

        }



    # ======================================================
    # ORIENTATION
    # ======================================================

    def add_orientation_constraint(
        self,
        side,
        data
    ):

        self.constraints["orientation"][side] = data



    # ======================================================
    # SETBACK
    # ======================================================

    def add_setback(
        self,
        side,
        value
    ):

        self.constraints["setbacks"][side] = value



    # ======================================================
    # YARDS
    # ======================================================

    def add_yard(
        self,
        name,
        width=None,
        area=None
    ):

        self.constraints["yards"][name] = {


            "width": width,


            "area": area

        }



    # ======================================================
    # COVERAGE
    # ======================================================

    def set_coverage(
        self,
        value
    ):

        self.constraints["coverage"] = value



    # ======================================================
    # DENSITY
    # ======================================================

    def set_density(
        self,
        value
    ):

        self.constraints["density"] = value



    # ======================================================
    # BUILDING POSITION
    # ======================================================

    def set_building_position(
        self,
        position
    ):

        self.constraints["building_position"] = position



    # ======================================================
    # LIGHT WELL
    # ======================================================

    def add_light_well(
        self,
        name,
        from_floor=None,
        to_floor=None,
        area=None
    ):

        self.constraints["light_wells"].append({

            "name": name,

            "from_floor": from_floor,

            "to_floor": to_floor,

            "area": area

        })



    # ======================================================
    # ACCESS
    # ======================================================

    def add_access(
        self,
        access_type,
        data
    ):

        self.constraints["access"][access_type] = data



    # ======================================================
    # PARKING CONSTRAINT
    # ======================================================

    def add_parking_constraint(
        self,
        name,
        value
    ):

        self.constraints["parking_constraints"][name] = value



    # ======================================================
    # REGULATION
    # ======================================================

    def add_regulation(
        self,
        name,
        value
    ):

        self.constraints["regulations"][name] = value



    # ======================================================
    # OPEN SPACE
    # ======================================================

    def add_open_space(
        self,
        name,
        area=None
    ):

        self.constraints["open_spaces"].append({

            "name": name,

            "area": area

        })



    # ======================================================
    # EXPORT
    # ======================================================

    def export(self):

        return self.constraints