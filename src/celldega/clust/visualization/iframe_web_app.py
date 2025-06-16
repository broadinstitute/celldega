from pathlib import Path

from IPython.display import IFrame, display
import requests


try:
    import StringIO
except ImportError:
    from io import StringIO


def main(net, filename: str | Path | None = None, width: int = 1000, height: int = 800) -> str:
    """
    Upload matrix data to Clustergrammer web service and display in iframe.

    This function takes a Network object and either uploads its matrix data
    directly (when filename=None) or uploads a specified file to the
    Clustergrammer web service, then displays the result in an IPython iframe.

    Args:
        net: Network object with write_matrix_to_tsv() method and dat attribute
        filename: Optional path to file to upload. If None, uses net.write_matrix_to_tsv()
        width: Width of the iframe in pixels (default: 1000)
        height: Height of the iframe in pixels (default: 800)

    Returns:
        str: URL link to the uploaded visualization

    Raises:
        requests.RequestException: If the HTTP request fails
        FileNotFoundError: If the specified filename doesn't exist
        KeyError: If net.dat doesn't contain required 'filename' key when filename=None
    """
    # Use HTTPS for security
    clustergrammer_url = "https://amp.pharm.mssm.edu/clustergrammer/matrix_upload/"

    try:
        if filename is None:
            # Generate matrix data from network object
            file_string = net.write_matrix_to_tsv()
            file_obj = StringIO(file_string)

            # Use network filename or default fallback
            fake_filename = "Network.txt" if net.dat["filename"] is None else net.dat["filename"]

            # Upload using StringIO object
            response = requests.post(
                clustergrammer_url,
                files={"file": (fake_filename, file_obj)},
                timeout=30,  # Add reasonable timeout
            )
        else:
            # Upload specified file with proper resource management
            with Path(filename).open("rb") as file_obj:
                response = requests.post(
                    clustergrammer_url,
                    files={"file": file_obj},
                    timeout=30,  # Add reasonable timeout
                )

        # Validate response
        response.raise_for_status()  # Raises HTTPError for bad responses

        link = response.text

        # Validate that we got a reasonable response
        if not link or not isinstance(link, str):
            raise ValueError("Invalid response from server: expected URL string")

        # Display the result
        display(IFrame(link, width=width, height=height))

        return link

    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to upload to Clustergrammer service: {e}") from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Could not find file: {filename}") from e
    except KeyError as e:
        raise KeyError(f"Network object missing required data: {e}") from e
