"""Generate the SmartPark AWS architecture diagram.

Renders docs/architecture/smartpark-architecture.png: a minimal, five-node
view of the real resources in infra/template.yaml, meant to be readable at
a glance.

    AWS Amplify -> API Gateway -> Lambda -> DynamoDB
                                        \\-> Bedrock

Requires the `diagrams` package (Graphviz-based) and the `dot` binary.
This script only renders a static PNG; it makes no AWS calls and deploys
nothing.

Usage:
    backend/.venv/bin/python docs/architecture/generate_diagram.py
"""

from diagrams import Diagram, Edge
from diagrams.aws.mobile import Amplify
from diagrams.aws.network import APIGateway
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.general import General  # no dedicated Bedrock icon in this
                                            # diagrams version; labeled below

OUTPUT_BASENAME = "smartpark-architecture"  # diagrams appends ".png"

graph_attr = {
    "fontsize": "22",
    "bgcolor": "white",
    "pad": "0.6",
    "splines": "line",
    "nodesep": "1.1",
    "ranksep": "1.3",
}

node_attr = {
    "fontsize": "14",
}

with Diagram(
    "SmartPark \u2014 AWS architecture",
    filename=OUTPUT_BASENAME,
    show=False,
    direction="LR",
    outformat="png",
    graph_attr=graph_attr,
    node_attr=node_attr,
):
    frontend = Amplify("Amplify\n(frontend)")
    api = APIGateway("API Gateway")
    fn = Lambda("Lambda")
    table = Dynamodb("DynamoDB")
    bedrock = General("Bedrock")

    frontend >> Edge(color="#232F3E") >> api >> Edge(color="#232F3E") >> fn
    fn >> Edge(color="#1A73E8") >> table
    fn >> Edge(color="#D86613") >> bedrock

print(f"Wrote {OUTPUT_BASENAME}.png")
