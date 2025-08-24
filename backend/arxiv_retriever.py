import arxiv
import os
import tempfile
import requests
import uuid 

def retrieve_arxiv_papers(query: str, max_results: int, download_pdfs: bool = False):

    """
    Retrieve papers from arXiv based on a search query.

    Args:
        query (str): The search query for arXiv.
        max_results (int): The maximum number of results to return.

    Returns:
        list: A list of dictionaries containing paper details.
    """
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    
    results = []
    for result in search.results():
        arxiv_id = result.get_short_id()
        pdf_path = None
        if download_pdfs:
            pdf_path = download_pdf(result.pdf_url, arxiv_id)

        results.append ({
            'title': result.title.strip(),
            'authors': [author.name for author in result.authors],
            'summary': result.summary.strip(),
            'pdf_url': result.pdf_url,
            'published': result.published.strftime("%Y-%m-%d"),
            'arxiv_id': arxiv_id,
            'primary_category': result.primary_category,
            'categories': result.categories,
            'pdf_path': pdf_path
        })
    
    return results

def download_pdf(url, arxiv_id):
    try:
        response = requests.get(url, timeout=15)
        safe_arxiv_id = arxiv_id.replace('/', '_')
        response.raise_for_status()
        temp_dir = tempfile.gettempdir()
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        filename = os.path.join(temp_dir, f"{safe_arxiv_id}_{uuid.uuid4().hex}.pdf")
        with open(filename, "wb") as f:
            f.write(response.content)
        return filename
    except Exception as e:
        print(f"failed to download {url}: {e}")
        return None
