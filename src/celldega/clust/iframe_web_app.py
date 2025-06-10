def main(net, filename=None, width=1000, height=800):
    # from io import StringIO
    from pathlib import Path

    from IPython.display import IFrame, display
    import requests

    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

    clustergrammer_url = "http://amp.pharm.mssm.edu/clustergrammer/matrix_upload/"

    if filename is None:
        file_string = net.write_matrix_to_tsv()
        file_obj = StringIO(file_string)

        fake_filename = "Network.txt" if net.dat["filename"] is None else net.dat["filename"]

        r = requests.post(clustergrammer_url, files={"file": (fake_filename, file_obj)})
    else:
        file_obj = Path.open(filename)
        r = requests.post(clustergrammer_url, files={"file": file_obj})

    link = r.text

    display(IFrame(link, width=width, height=height))

    return link
