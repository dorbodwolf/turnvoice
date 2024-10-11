class Segment:
    """
    Represents a segment with start and end times and text.
    """

    def __init__(self, 
                 text: str,
                 start: float,
                 end: float,
                 ):

        """
        Initializes a Word object with text,
        start time, end time, and probability.
        """
        self.text = text
        self.start = start
        self.end = end

    def to_dict(self):
        """
        Returns a dictionary representation of the Word object.
        """
        return {
            'text': self.text,
            'start': self.start,
            'end': self.end,
        }

    @staticmethod
    def from_dict(data):
        """
        Creates a Word object from a dictionary.
        """
        return Segment(**data)
