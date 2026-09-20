from mcp.server.mcpserver import MCPServer
server=MCPServer('probe')
@server.tool()
def echo_probe(value: str) -> dict:
    """Return the supplied probe string without filesystem or network access."""
    return {'echo': value}
if __name__=='__main__': server.run(transport='stdio')
