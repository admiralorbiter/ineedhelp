class AdaptivePromptManager:
    def __init__(self, student_profile):
        self.profile = student_profile
        
    def get_prompt_style(self):
        """Determine appropriate prompt style based on student profile"""
        if self.profile.skill_level == 'advanced':
            return {
                'verbosity': 'concise',
                'hint_frequency': 'low',
                'example_frequency': 'minimal',
                'question_style': 'challenging'
            }
        elif self.profile.skill_level == 'intermediate':
            return {
                'verbosity': 'moderate',
                'hint_frequency': 'medium',
                'example_frequency': 'when_needed',
                'question_style': 'balanced'
            }
        else:  # beginner
            return {
                'verbosity': 'detailed',
                'hint_frequency': 'high',
                'example_frequency': 'frequent',
                'question_style': 'supportive'
            }
    
    def get_reading_level_instructions(self):
        """Get language complexity instructions based on reading level"""
        reading_level = self.profile.reading_level
        
        if reading_level in ['K', 'G1', 'G2', 'G3']:
            return {
                'vocabulary': 'simple',
                'sentence_length': 'short',
                'explanation_style': 'basic',
                'examples': 'concrete and familiar'
            }
        elif reading_level in ['G4', 'G5', 'G6']:
            return {
                'vocabulary': 'grade-appropriate',
                'sentence_length': 'moderate',
                'explanation_style': 'clear',
                'examples': 'relatable'
            }
        elif reading_level in ['G7', 'G8', 'G9']:
            return {
                'vocabulary': 'advanced',
                'sentence_length': 'varied',
                'explanation_style': 'detailed',
                'examples': 'abstract'
            }
        else:  # G10-G12
            return {
                'vocabulary': 'sophisticated',
                'sentence_length': 'complex',
                'explanation_style': 'comprehensive',
                'examples': 'complex and abstract'
            }

    def generate_adaptive_prompt(self, base_prompt):
        """Modify the base prompt based on student's profile"""
        style = self.get_prompt_style()
        reading_level = self.get_reading_level_instructions()
        
        # Add reading level instructions
        reading_instructions = f"""
        Please adjust your language complexity for a {self.profile.reading_level} reading level:
        - Use {reading_level['vocabulary']} vocabulary
        - Use {reading_level['sentence_length']} sentences
        - Provide {reading_level['explanation_style']} explanations
        - Use {reading_level['examples']} examples
        """
        
        # Combine all adaptations
        adapted_prompt = base_prompt + reading_instructions
        
        # Add style-specific instructions
        if style['verbosity'] == 'detailed':
            adapted_prompt += "\nPlease provide detailed explanations with examples."
        elif style['verbosity'] == 'moderate':
            adapted_prompt += "\nProvide balanced explanations with occasional examples."
        else:
            adapted_prompt += "\nFocus on key concepts with minimal elaboration."
        
        # Add performance-based modifications
        if self.profile.consecutive_failures > 2:
            adapted_prompt += "\nThe student is currently struggling. Provide more supportive guidance and break down concepts into smaller steps."
        
        return adapted_prompt 