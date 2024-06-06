


class Log:
    status: str
    message: str
    message_color: str



    def __init__(self, status:str, message: str):
        self.status = status
        self.message = message

    

    def get_status_color(self, status: str):
        """
        Convert the color string to the corresponding ANSI color code
        """
        colors = {
            "regular": "\033[30m",  # black
            "fail": "\033[31m",     # red
            "success": "\033[32m",  # green
            "warning": "\033[33m",  # yellow
            "info": "\033[34m",     # blue
        }

        return colors.get(status, colors["regular"])
        


    
    def print_message(self):
        """
        Print the message in the specified color
        """
        color = self.get_status_color(self.status)
        print(color + self.message + "\033[0m")