# ==================================================
# ArchitectOS File Upload Adapter v1.0
# Flask Upload -> File Intelligence Contract
# ==================================================


class FileUploadAdapter:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📦 File Upload Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def adapt(
        self,
        uploaded_file
    ):

        if not uploaded_file:

            return {

                "status":
                "error",

                "message":
                "empty file"

            }



        filename = uploaded_file.filename


        return {

            "filename":
            filename,


            "extension":
            self._extension(
                filename
            ),


            "content_type":
            uploaded_file.content_type,


            "file_object":
            uploaded_file

        }



    # ==================================================
    # EXTENSION
    # ==================================================

    def _extension(
        self,
        filename
    ):

        if not filename:

            return ""


        import os


        return os.path.splitext(
            filename
        )[1].lower()