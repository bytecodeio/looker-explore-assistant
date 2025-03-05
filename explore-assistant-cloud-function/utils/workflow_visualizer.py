import os
import logging
from graphviz import Digraph
from typing import Dict, List, Optional, Tuple

class WorkflowVisualizer:
    """
    Utility to generate visualization diagrams of the Looker Explore workflow.
    Creates annotated flowcharts showing the component relationships and data flow.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the workflow visualizer
        
        Args:
            output_dir: Directory where the diagram files will be saved
                        If None, uses the current directory
        """
        self.output_dir = output_dir or os.getcwd()
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def generate_workflow_diagram(self, filename: str = "looker_explore_workflow", 
                                  include_llm_info: bool = True,
                                  include_data_flow: bool = True,
                                  include_feedback: bool = True) -> str:
        """
        Generate a visualization of the Looker Explore workflow
        
        Args:
            filename: Name of the output file (without extension)
            include_llm_info: Whether to include information about LLM models used
            include_data_flow: Whether to include details about data flowing between nodes
            include_feedback: Whether to include the feedback handling flow
            
        Returns:
            Path to the generated diagram file
        """
        # Create a new directed graph
        dot = Digraph(comment='Looker Explore Assistant Workflow')
        dot.attr(rankdir='TB', size='12,10', dpi='300')
        
        # Define node styles
        dot.attr('node', shape='box', style='rounded,filled', 
                 fontname='Arial', fontsize='12', margin='0.2,0.1')
        
        # Define edge styles
        dot.attr('edge', fontname='Arial', fontsize='10')
        
        # Define clusters/subgraphs for logical grouping
        # User Interaction
        with dot.subgraph(name='cluster_user') as c:
            c.attr(label='User Interaction', style='filled', color='lightgrey', fontname='Arial Bold')
            c.node('user_query', 'User Query\n(Input Question)', fillcolor='#D6EAF8')
            c.node('user_feedback', 'User Feedback', fillcolor='#D6EAF8')
            c.node('user_verification', 'User Verification', fillcolor='#D6EAF8')
            c.node('response', 'Final Response\n(Answer + Visualization)', fillcolor='#D6EAF8')
        
        # Explore Selection & Understanding
        with dot.subgraph(name='cluster_selection') as c:
            c.attr(label='Exploration Selection', style='filled', color='lightgrey')
            c.node('query_node', 'Query Processing\n(Parse User Question)', fillcolor='#D5F5E3')
            c.node('explore_selection', 'Explore Selection\n(Find Relevant Data Model)', fillcolor='#D5F5E3')
            c.node('semantic_model', 'Semantic Model Loading\n(Retrieve Field Metadata)', fillcolor='#D5F5E3')
        
        # Parameter Generation
        with dot.subgraph(name='cluster_params') as c:
            c.attr(label='Parameter Generation', style='filled', color='lightgrey')
            c.node('params_gen', 'Explore Parameters Generation\n(Claude 3.7 Sonnet - Complex Reasoning)', 
                   fillcolor='#FCF3CF', color='darkgoldenrod2')
            c.node('filter_values', 'Filter Value Fetcher\n(Query for Real Filter Values)', fillcolor='#FCF3CF')
        
        # Execution & Summarization
        with dot.subgraph(name='cluster_execution') as c:
            c.attr(label='Execution & Summarization', style='filled', color='lightgrey')
            c.node('execute', 'Execute Explore\n(Run the Generated Query)', fillcolor='#FADBD8')
            c.node('summarize', 'Data Summarization\n(Extract Insights)', fillcolor='#FADBD8')
        
        # Feedback Processing (only if include_feedback is True)
        if include_feedback:
            with dot.subgraph(name='cluster_feedback') as c:
                c.attr(label='Feedback Processing', style='filled', color='lightgrey', fontcolor='darkblue')
                c.node('feedback_detection', 'Feedback Detection\n(Analyze User Complaint)', fillcolor='#AED6F1')
                c.node('explore_regen', 'Explore Regeneration\n(Improve Based on Feedback)', fillcolor='#AED6F1')
                c.node('verification_node', 'Verification Request\n(Ask User If Improved)', fillcolor='#AED6F1')
                c.node('example_storage', 'Example Storage\n(Save Successful Improvements)', fillcolor='#AED6F1')
        
        # Add connections/edges for main flow
        dot.edge('user_query', 'query_node')
        dot.edge('query_node', 'explore_selection', label='Processed Question' if include_data_flow else '')
        dot.edge('explore_selection', 'semantic_model', label='Selected Explore' if include_data_flow else '')
        dot.edge('semantic_model', 'params_gen', label='Field Metadata' if include_data_flow else '')
        dot.edge('params_gen', 'filter_values', label='Initial Parameters' if include_data_flow else '')
        dot.edge('filter_values', 'execute', label='Enhanced Parameters' if include_data_flow else '')
        dot.edge('execute', 'summarize', label='Query Results' if include_data_flow else '')
        dot.edge('summarize', 'response')
        
        # Add connections/edges for feedback flow
        if include_feedback:
            dot.edge('response', 'user_feedback', style='dashed', constraint='false')
            dot.edge('user_feedback', 'feedback_detection')
            dot.edge('feedback_detection', 'explore_regen', label='If complaint detected')
            
            # Connect feedback flow back to main flow
            dot.edge('explore_regen', 'filter_values', style='dashed', color='blue', constraint='false')
            dot.edge('execute', 'verification_node', style='dashed', color='blue', constraint='false')
            dot.edge('verification_node', 'user_verification', style='dashed', color='blue')
            dot.edge('user_verification', 'example_storage', style='dashed', color='blue')
            
            # Add decision diamond
            dot.node('feedback_decision', 'Needs\nRegeneration?', shape='diamond', fillcolor='#F5B7B1')
            dot.edge('feedback_detection', 'feedback_decision', constraint='false')
            dot.edge('feedback_decision', 'explore_regen', label='Yes')
            dot.edge('feedback_decision', 'response', label='No', constraint='false')
            
            # Add verification diamond
            dot.node('verification_decision', 'Is Correct?', shape='diamond', fillcolor='#F5B7B1')
            dot.edge('user_verification', 'verification_decision', style='dashed', color='blue')
            dot.edge('verification_decision', 'example_storage', label='Yes', style='dashed', color='blue')
            dot.edge('verification_decision', 'user_feedback', label='No', style='dashed', color='blue', constraint='false')
        
        # Add LLM model information if requested
        if include_llm_info:
            dot.node('model_fast', 'Fast Model\n(Gemini Pro)', shape='note', fillcolor='#E8DAEF')
            dot.node('model_thinking', 'Thinking Model\n(Claude 3.7 Sonnet)', shape='note', fillcolor='#E8DAEF')
            dot.node('model_summary', 'Summary Model\n(Gemini Pro)', shape='note', fillcolor='#E8DAEF')
            dot.node('model_filter', 'Filter Model\n(Gemini Pro)', shape='note', fillcolor='#E8DAEF')
            
            # Connect models to nodes using dashed lines
            dot.edge('model_fast', 'explore_selection', style='dashed', color='gray')
            dot.edge('model_fast', 'filter_values', style='dashed', color='gray')
            dot.edge('model_thinking', 'params_gen', style='dashed', color='gray')
            dot.edge('model_summary', 'summarize', style='dashed', color='gray')
            
            if include_feedback:
                dot.edge('model_fast', 'feedback_detection', style='dashed', color='gray')
                dot.edge('model_thinking', 'explore_regen', style='dashed', color='gray')
        
        # Add conditionals and decision points
        dot.node('check_explore', 'Selected\nExplore?', shape='diamond', fillcolor='#F5B7B1')
        dot.node('check_semantic', 'Semantic Model\nLoaded?', shape='diamond', fillcolor='#F5B7B1')
        
        # Insert decision points into flow
        dot.edge('explore_selection', 'check_explore')
        dot.edge('check_explore', 'semantic_model', label='Yes')
        dot.edge('check_explore', 'response', label='No', constraint='false')
        
        dot.edge('semantic_model', 'check_semantic')
        dot.edge('check_semantic', 'params_gen', label='Yes')
        dot.edge('check_semantic', 'response', label='No', constraint='false')
        
        # Save the diagram
        output_path = os.path.join(self.output_dir, filename)
        dot.render(output_path, format='png', cleanup=True)
        
        logging.info(f"Workflow diagram generated at: {output_path}.png")
        return f"{output_path}.png"
    
    def generate_feedback_flow_diagram(self, filename: str = "feedback_flow_diagram") -> str:
        """
        Generate a visualization specifically for the feedback flow
        
        Args:
            filename: Name of the output file (without extension)
            
        Returns:
            Path to the generated diagram file
        """
        # Create a new directed graph
        dot = Digraph(comment='Feedback Processing Flow')
        dot.attr(rankdir='TB', size='10,8', dpi='300')
        
        # Define node styles
        dot.attr('node', shape='box', style='rounded,filled', 
                 fontname='Arial', fontsize='12', margin='0.2,0.1')
        
        # Define edge styles
        dot.attr('edge', fontname='Arial', fontsize='10')
        
        # User nodes
        dot.node('initial_response', 'Initial Explore Response', fillcolor='#D6EAF8')
        dot.node('user_feedback', 'User Feedback', fillcolor='#D6EAF8')
        dot.node('user_verification', 'User Verification', fillcolor='#D6EAF8')
        dot.node('final_response', 'Final Response', fillcolor='#D6EAF8')
        
        # Processing nodes
        dot.node('feedback_detection', 'Feedback Detection\n(Analyze User Input)', fillcolor='#AED6F1')
        dot.node('explore_regen', 'Explore Regeneration\n(Improve Based on Feedback)', fillcolor='#AED6F1')
        dot.node('execute_explore', 'Execute Explore\n(Run New Query)', fillcolor='#AED6F1')
        dot.node('verification_request', 'Verification Request\n(Ask If Improved)', fillcolor='#AED6F1')
        dot.node('example_storage', 'Example Storage\n(Save to BigQuery)', fillcolor='#AED6F1')
        
        # Decision nodes
        dot.node('needs_regen', 'Needs\nRegeneration?', shape='diamond', fillcolor='#F5B7B1')
        dot.node('is_correct', 'Is\nCorrect?', shape='diamond', fillcolor='#F5B7B1')
        
        # Add flows
        dot.edge('initial_response', 'user_feedback', label='User provides feedback')
        dot.edge('user_feedback', 'feedback_detection')
        dot.edge('feedback_detection', 'needs_regen')
        
        # No regeneration needed
        dot.edge('needs_regen', 'final_response', label='No')
        
        # Regeneration flow
        dot.edge('needs_regen', 'explore_regen', label='Yes')
        dot.edge('explore_regen', 'execute_explore')
        dot.edge('execute_explore', 'verification_request')
        dot.edge('verification_request', 'user_verification')
        dot.edge('user_verification', 'is_correct')
        
        # Verification results
        dot.edge('is_correct', 'example_storage', label='Yes')
        dot.edge('example_storage', 'final_response')
        dot.edge('is_correct', 'user_feedback', label='No', constraint='false')
        
        # Save the diagram
        output_path = os.path.join(self.output_dir, filename)
        dot.render(output_path, format='png', cleanup=True)
        
        logging.info(f"Feedback flow diagram generated at: {output_path}.png")
        return f"{output_path}.png"
        
    def generate_conditional_flow_diagram(self, filename: str = "conditional_document_flow") -> str:
        """
        Generate a visualization of the conditional document loading flow
        
        Args:
            filename: Name of the output file (without extension)
            
        Returns:
            Path to the generated diagram file
        """
        # Create a new directed graph
        dot = Digraph(comment='Conditional Document Loading Flow')
        dot.attr(rankdir='TB', size='11,8', dpi='300')
        
        # Define node styles
        dot.attr('node', shape='box', style='rounded,filled', 
                 fontname='Arial', fontsize='12', margin='0.2,0.1')
        
        # Define edge styles
        dot.attr('edge', fontname='Arial', fontsize='10')
        
        # Document sources
        dot.node('user_query', 'User Query', fillcolor='#D6EAF8')
        dot.node('query_analyzer', 'Query Analyzer', fillcolor='#D5F5E3')
        
        # Decision diamonds
        dot.node('check_viz', 'Needs\nVisualization?', shape='diamond', fillcolor='#F5B7B1')
        dot.node('check_pivot', 'Needs\nPivot?', shape='diamond', fillcolor='#F5B7B1')
        
        # Document nodes
        dot.node('filter_doc', 'Filter Documentation\n(Always Included)', fillcolor='#FADBD8')
        dot.node('interval_doc', 'Interval/Timeframes\n(Always Included)', fillcolor='#FADBD8')
        dot.node('viz_doc', 'Visualization Documentation', fillcolor='#FADBD8')
        dot.node('pivot_doc', 'Pivot Documentation', fillcolor='#FADBD8')
        
        # Context generation
        dot.node('context_gen', 'Generate Shared Context', fillcolor='#FCF3CF')
        
        # Add flows
        dot.edge('user_query', 'query_analyzer')
        dot.edge('query_analyzer', 'check_viz')
        dot.edge('query_analyzer', 'check_pivot')
        
        dot.edge('check_viz', 'viz_doc', label='Yes')
        dot.edge('check_viz', 'context_gen', label='No', constraint='false')
        
        dot.edge('check_pivot', 'pivot_doc', label='Yes')
        dot.edge('check_pivot', 'context_gen', label='No', constraint='false')
        
        dot.edge('filter_doc', 'context_gen')
        dot.edge('interval_doc', 'context_gen')
        dot.edge('viz_doc', 'context_gen')
        dot.edge('pivot_doc', 'context_gen')
        
        # Save the diagram
        output_path = os.path.join(self.output_dir, filename)
        dot.render(output_path, format='png', cleanup=True)
        
        logging.info(f"Conditional document flow diagram generated at: {output_path}.png")
        return f"{output_path}.png"

    def generate_model_selection_diagram(self, filename: str = "model_selection_flow") -> str:
        """
        Generate a visualization of the model selection strategy
        
        Args:
            filename: Name of the output file (without extension)
            
        Returns:
            Path to the generated diagram file
        """
        # Create a new directed graph
        dot = Digraph(comment='Model Selection Strategy')
        dot.attr(rankdir='TB', size='11,8', dpi='300')
        
        # Define node styles
        dot.attr('node', shape='box', style='rounded,filled', 
                 fontname='Arial', fontsize='12', margin='0.2,0.1')
        
        # Define edge styles
        dot.attr('edge', fontname='Arial', fontsize='10')
        
        # Task nodes
        dot.node('workflow', 'Workflow Step', shape='oval', fillcolor='#D6EAF8')
        
        # Models
        dot.node('model_manager', 'Model Manager', shape='component', fillcolor='#D5F5E3')
        
        # Task type decision diamond
        dot.node('task_type', 'Task Type?', shape='diamond', fillcolor='#F5B7B1')
        
        # Model nodes
        dot.node('fast_model', 'Fast Model\n(Gemini Pro)', fillcolor='#FADBD8')
        dot.node('thinking_model', 'Thinking Model\n(Claude 3.7 Sonnet)', fillcolor='#FADBD8')
        dot.node('summary_model', 'Summary Model\n(Gemini Pro)', fillcolor='#FADBD8')
        dot.node('filter_model', 'Filter Model\n(Gemini Pro)', fillcolor='#FADBD8')
        
        # Add flows
        dot.edge('workflow', 'model_manager', label='Request model for task')
        dot.edge('model_manager', 'task_type')
        
        dot.edge('task_type', 'fast_model', label='Simple tasks\n(explore_selection, etc.)')
        dot.edge('task_type', 'thinking_model', label='Complex reasoning\n(explore_params_generation)')
        dot.edge('task_type', 'summary_model', label='Summarization\n(data insights)')
        dot.edge('task_type', 'filter_model', label='Filter selection\n(choosing values)')
        
        dot.edge('fast_model', 'workflow', constraint='false', style='dashed', label='Return model')
        dot.edge('thinking_model', 'workflow', constraint='false', style='dashed', label='Return model')
        dot.edge('summary_model', 'workflow', constraint='false', style='dashed', label='Return model')
        dot.edge('filter_model', 'workflow', constraint='false', style='dashed', label='Return model')
        
        # Save the diagram
        output_path = os.path.join(self.output_dir, filename)
        dot.render(output_path, format='png', cleanup=True)
        
        logging.info(f"Model selection diagram generated at: {output_path}.png")
        return f"{output_path}.png"
        
def generate_workflow_diagrams(output_dir: str = None) -> Dict[str, str]:
    """
    Generate all workflow-related diagrams
    
    Args:
        output_dir: Directory where diagram files will be saved
        
    Returns:
        Dictionary mapping diagram names to their file paths
    """
    visualizer = WorkflowVisualizer(output_dir)
    
    diagrams = {
        'workflow': visualizer.generate_workflow_diagram(),
        'feedback_flow': visualizer.generate_feedback_flow_diagram(),
        'conditional_docs': visualizer.generate_conditional_flow_diagram(),
        'model_selection': visualizer.generate_model_selection_diagram()
    }
    
    return diagrams

if __name__ == "__main__":
    # If this script is run directly, generate all diagrams
    diagrams = generate_workflow_diagrams()
    for name, path in diagrams.items():
        print(f"{name}: {path}")
