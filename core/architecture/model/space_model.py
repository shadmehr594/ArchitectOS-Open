class SpaceModel:


    def __init__(
        self,
        name,
        category=None
    ):

        self.name = name

        self.category = category

        self.properties = {}

        self.relationships = []


    def add_property(
        self,
        key,
        value
    ):

        self.properties[key] = value


    def add_relationship(
        self,
        target,
        relation
    ):

        self.relationships.append(
            {
                "target": target,
                "relation": relation
            }
        )


    def to_dict(self):

        return {

            "name": self.name,

            "category": self.category,

            "properties": self.properties,

            "relationships": self.relationships

        }