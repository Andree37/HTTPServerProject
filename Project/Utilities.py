"""
 Utilities for the http server

"""

from threading import Semaphore


# Singleton Logger
class Logger:
    __instance = None

    @staticmethod
    def get_instance():
        if Logger.__instance is None:
            Logger()
        return Logger.__instance

    def __init__(self):
        self.filename = "log.txt"
        if Logger.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Logger.__instance = self

    # Write to file the message (IP and URL)
    def write_to_file(self, message):
        file = None
        try:
            file = open(self.filename, "a")
            file.write(message)
        except FileNotFoundError:
            print("Couldn't find file")
        finally:
            if file is not None:
                file.close()


# Class Statistics, responsible for keeping a statistics of the cache
class Statistics:
    def __init__(self):
        self.visited_links = {}
        self.sem_write = Semaphore()
    # link -> response
    #      -> times

    # Each time the user visits a link, this takes care of it and keeps it in a dictionary with the response, times it
    # was requested and the link itself
    def visit_link(self, link, response):
        # Semaphore to make sure there is no one writing at the same time
        self.sem_write.acquire()
        # If link is already created here, theres no point on rewriting it all, just count the times
        if link in self.visited_links:
            dic = self.visited_links[link]
            times = dic["times"]
            times += 1
            dic["times"] = times
        else:
            times = 1
            self.visited_links[link] = {"response": response, "times": times, "link": link}
        self.sem_write.release()

    # Get the n most visited links in the server
    def get_n_most_visited_links(self, n=2):
        self.sem_write.acquire()
        most_visited = []
        visited_links = self.visited_links.copy()
        # Search on dictionary the most visited
        for v in visited_links.values():
            times_visited = v["times"]

            position = 0
            for link in most_visited:
                link = link["link"]
                dic = visited_links[link]
                times = dic["times"]
                if times_visited < times:
                    position += 1
                    # To save compute power , we don't have to order the n+ positions of the array and we put it on the
                    # n position
                    if position == n:
                        break
            most_visited.insert(position, v)

        self.sem_write.release()
        # Return only the n most visited links
        return most_visited[0:n]

    # Get the link if it's in the most visited links, None if it isn't
    def get_link_in_most_visited(self, link):
        most_visited = self.get_n_most_visited_links()

        for item in most_visited:
            for k, v in item.items():
                if v == link:
                    return item["response"]
        return None
